"""
AstrBot 长期记忆插件：基于 Hindsight 的 Agent 记忆

在每次请求大模型前：
1. 将当前轮次对话内容存入 Hindsight（retain）
2. 根据当前问题召回长期记忆（recall）
3. 将召回的记忆插入到多轮对话的提示中，再发送给大模型
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

try:
    from hindsight_client import Hindsight
except ImportError:
    Hindsight = None  # type: ignore[misc, assignment]

try:
    from forget_previous_images import forget_previous_images_in_contexts, _content_has_image as _content_has_image_fn
except ImportError:
    forget_previous_images_in_contexts = None
    _content_has_image_fn = None

try:
    from image_retain import extract_image_payloads_from_contexts, retain_images_async
except ImportError:
    extract_image_payloads_from_contexts = None  # type: ignore[misc, assignment]
    retain_images_async = None  # type: ignore[misc, assignment]


def _get_text_from_content(content: Any) -> str:
    """从单条消息的 content 中提取纯文本（兼容多模态）。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and "text" in item:
                    parts.append(item["text"])
            elif hasattr(item, "text"):
                parts.append(getattr(item, "text", ""))
        return " ".join(parts).strip()
    return str(content).strip()


def _recall_item_text(r: Any) -> str:
    """从 recall 单条结果中取文本，兼容对象或字符串。"""
    if isinstance(r, str):
        return r.strip()
    return getattr(r, "text", str(r)).strip() if r else ""


def _content_has_image(content: Any) -> bool:
    """判断消息 content 是否包含图片（用于在长期记忆中保留「发过图」的痕迹）。"""
    if _content_has_image_fn is not None:
        return _content_has_image_fn(content)
    return False


def _build_retain_content(req: ProviderRequest, max_messages: int = 6) -> str:
    """从当前请求中构建要存入记忆的文本（本轮用户输入 + 最近 max_messages 轮对话）；含图消息会保留「附有图片」以便召回。"""
    parts = []
    if req.contexts:
        for ctx in req.contexts[-max_messages:]:
            role = (ctx.get("role") or "").strip().lower()
            raw_content = ctx.get("content")
            content = _get_text_from_content(raw_content)
            has_image = _content_has_image(raw_content)
            if role == "user":
                if content:
                    parts.append(f"用户: {content}" + (" [附有一张图片]" if has_image else ""))
                elif has_image:
                    parts.append("用户: 发送了一张图片")
            elif role == "assistant":
                if content:
                    parts.append(f"助手: {content}" + (" [附有图片]" if has_image else ""))
                elif has_image:
                    parts.append("助手: 回复中包含图片")
    if req.prompt and isinstance(req.prompt, str) and req.prompt.strip():
        parts.append(f"用户: {req.prompt.strip()}")
    return "\n".join(parts).strip() if parts else ""


@register(
    "hindsight_memory",
    "AstrBot Hindsight",
    "基于 Hindsight 的长期记忆：在发送给大模型前自动存入记忆并召回长期记忆注入到多轮对话中。",
    "0.1.0",
)
class HindsightMemoryPlugin(Star):
    """Hindsight 长期记忆插件：使用 Hindsight 客户端在 LLM 请求前 retain/recall 并注入记忆。"""

    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context, config)
        self._config = config or {}
        self._client: Hindsight | None = None
        self._client_base_url: str = ""
        self._enabled = bool(self._config.get("enabled", True))
        self._base_url = (self._config.get("base_url") or "http://localhost:8888").strip().rstrip("/")
        self._timeout = float(self._config.get("timeout", 30))
        self._recall_budget = (self._config.get("recall_budget") or "mid").lower()
        if self._recall_budget not in ("low", "mid", "high"):
            self._recall_budget = "mid"
        self._recall_max_tokens = int(self._config.get("recall_max_tokens", 2048))
        self._memory_system_prompt = self._config.get("memory_system_prompt") or (
            "以下是与当前对话相关的长期记忆，供你参考：\n\n{memory}\n\n请结合上述记忆自然地进行回复。"
        )
        self._retain_context = self._config.get("retain_context") or "astrbot_chat"
        self._retain_images = bool(self._config.get("retain_images", True))
        self._image_parser = (self._config.get("image_parser") or "").strip() or None
        self._retain_context_window = int(self._config.get("retain_context_window", 6))
        if self._retain_context_window < 1:
            self._retain_context_window = 6
        self._debug = bool(self._config.get("debug", False))
        if Hindsight is None:
            logger.warning("hindsight_memory: 未安装 hindsight-client，插件将不执行记忆逻辑。请 pip install hindsight-client")
        else:
            logger.info(
                "hindsight_memory: 已加载，base_url=%s, enabled=%s",
                self._base_url,
                self._enabled,
            )

    def _get_client(self) -> Hindsight | None:
        if Hindsight is None:
            return None
        if self._client is not None and self._client_base_url == self._base_url:
            return self._client
        try:
            self._client = Hindsight(base_url=self._base_url, timeout=self._timeout)
            self._client_base_url = self._base_url
            return self._client
        except Exception as e:
            logger.exception("hindsight_memory: 创建 Hindsight 客户端失败: %s", e)
            return None

    async def _retain(self, bank_id: str, content: str) -> None:
        """异步执行 retain：将内容存入 Hindsight。优先使用 aretain 避免 to_thread 与客户端内部 asyncio timeout 冲突。"""
        if not content.strip():
            return
        client = self._get_client()
        if client is None:
            return
        ts = datetime.now(timezone.utc)
        try:
            if callable(getattr(client, "aretain", None)):
                await client.aretain(
                    bank_id=bank_id,
                    content=content,
                    context=self._retain_context,
                    timestamp=ts,
                )
            else:
                await asyncio.to_thread(
                    client.retain,
                    bank_id=bank_id,
                    content=content,
                    context=self._retain_context,
                    timestamp=ts,
                )
        except Exception as e:
            logger.warning("hindsight_memory: retain 失败 (bank_id=%s): %s", bank_id, e)

    async def _recall(self, bank_id: str, query: str) -> list[str]:
        """异步执行 recall：根据 query 召回记忆，返回文本列表。优先使用 arecall 避免 to_thread 与客户端内部 asyncio timeout 冲突。"""
        if not query.strip():
            return []
        client = self._get_client()
        if client is None:
            return []
        try:
            if callable(getattr(client, "arecall", None)):
                response = await client.arecall(
                    bank_id=bank_id,
                    query=query,
                    budget=self._recall_budget,
                    max_tokens=self._recall_max_tokens,
                )
            else:
                response = await asyncio.to_thread(
                    client.recall,
                    bank_id=bank_id,
                    query=query,
                    budget=self._recall_budget,
                    max_tokens=self._recall_max_tokens,
                )
            # 兼容不同版本：RecallResponse.results 或 list，每项为对象(.text)或字符串
            if hasattr(response, "results"):
                return [_recall_item_text(r) for r in response.results if r is not None]
            if isinstance(response, list):
                return [_recall_item_text(r) for r in response if r is not None]
            return []
        except Exception as e:
            logger.warning("hindsight_memory: recall 失败 (bank_id=%s): %s", bank_id, e)
            return []

    @filter.on_llm_request(priority=100)
    async def on_req_llm(self, event: AstrMessageEvent, req: ProviderRequest) -> None:
        """在 LLM 请求前：先按完整上下文 retain/recall 并注入长期记忆（含「附有图片」），再对历史消息做「忘记图片」省 token。"""
        if not self._enabled or Hindsight is None:
            return
        bank_id = event.unified_msg_origin
        if self._debug:
            logger.info("hindsight_memory: on_req_llm 触发 bank_id=%s", bank_id)

        # 1) 构建本轮内容并 retain（与图片共用同一上下文窗口）
        retain_content = _build_retain_content(req, max_messages=self._retain_context_window)
        if retain_content:
            if self._debug:
                _log_trunc = retain_content[:200] + "..." if len(retain_content) > 200 else retain_content
                logger.info(
                    "hindsight_memory: 存入(retain) bank_id=%s 长度=%d 内容摘要: %s",
                    bank_id,
                    len(retain_content),
                    _log_trunc.replace("\n", " "),
                )
            await self._retain(bank_id, retain_content)
            if self._debug:
                logger.info("hindsight_memory: retain 已调用完成 bank_id=%s", bank_id)

        # 1b) 图片长期记忆：从最近 N 条消息中提取内联图片，通过 Hindsight retain_file 写入（OCR/视觉抽取后参与 recall）
        if (
            self._retain_images
            and req.contexts
            and extract_image_payloads_from_contexts is not None
            and retain_images_async is not None
        ):
            payloads = extract_image_payloads_from_contexts(req.contexts, max_messages=self._retain_context_window)
            if payloads:
                client = self._get_client()
                if client is not None:
                    try:
                        n = await retain_images_async(
                            client,
                            bank_id,
                            payloads,
                            context=self._retain_context,
                            parser=self._image_parser,
                        )
                        if n and self._debug:
                            logger.info("hindsight_memory: 图片 retain 完成 bank_id=%s 数量=%d", bank_id, n)
                    except Exception as e:
                        if self._debug:
                            logger.warning("hindsight_memory: 图片 retain 失败 bank_id=%s: %s", bank_id, e)

        # 2) 用当前用户问题做 recall
        query = req.prompt if isinstance(req.prompt, str) else ""
        if not query and req.contexts:
            for ctx in reversed(req.contexts):
                if (ctx.get("role") or "").strip().lower() == "user":
                    query = _get_text_from_content(ctx.get("content"))
                    break
        if not query:
            query = retain_content or "最近对话"
        if self._debug:
            _q = (query[:100] + "...") if len(query) > 100 else query
            logger.info("hindsight_memory: 查询(recall) bank_id=%s query=%s", bank_id, _q.replace("\n", " "))
        recalled = await self._recall(bank_id, query)
        if self._debug:
            combined = "\n".join(recalled).strip()
            _preview = (combined[:300] + "...") if len(combined) > 300 else combined
            logger.info(
                "hindsight_memory: 查出(recall) 返回 %d 条 bank_id=%s 内容摘要: %s",
                len(recalled),
                bank_id,
                _preview.replace("\n", " "),
            )
        if not recalled:
            if forget_previous_images_in_contexts is not None:
                forget_previous_images_in_contexts(req, keep_last_user_image=True)
            return

        # 3) 将长期记忆注入为一条 system 消息，插入到 contexts 最前（或第一条 system 之后）
        memory_text = "\n".join(recalled).strip()
        if not memory_text:
            if forget_previous_images_in_contexts is not None:
                forget_previous_images_in_contexts(req, keep_last_user_image=True)
            return
        # 使用 replace 避免用户模板中含其他 { } 时 format 报 KeyError
        system_content = self._memory_system_prompt.replace("{memory}", memory_text)
        inject_msg = {"role": "system", "content": system_content}

        if not req.contexts:
            req.contexts = [inject_msg]
            return
        # 若已有 system，插在第一个 system 之后，否则插在最前
        inserted = False
        for i, ctx in enumerate(req.contexts):
            if (ctx.get("role") or "").strip().lower() == "system":
                req.contexts.insert(i + 1, inject_msg)
                inserted = True
                break
        if not inserted:
            req.contexts.insert(0, inject_msg)

        # 4) 最后再「忘记之前的图片」：历史消息中的图片替换为占位符，仅保留当前轮图片，省 token 且长期记忆已保留「附有图片」
        if forget_previous_images_in_contexts is not None:
            forget_previous_images_in_contexts(req, keep_last_user_image=True)

    async def terminate(self) -> None:
        """插件卸载时关闭客户端。"""
        if self._client is not None:
            try:
                if callable(getattr(self._client, "close", None)):
                    self._client.close()
            except Exception as e:
                logger.debug("hindsight_memory: 关闭客户端时忽略: %s", e)
        self._client = None
        self._client_base_url = ""
        logger.info("hindsight_memory: 插件已卸载")
