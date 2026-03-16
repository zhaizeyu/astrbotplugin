"""
从多轮对话中提取图片并支持通过 Hindsight files/retain 写入长期记忆。

- 支持 content 中的 image_url（data:image/...;base64,xxx）与 inlineData（Gemini 格式）。
- 仅处理最近 N 条消息中的图片，与文本 retain 的窗口一致。
- 不拉取远程 URL 图片（避免超时与隐私），仅处理内联 base64。
"""

from __future__ import annotations

import asyncio
import base64
import re
from io import BytesIO
from typing import Any

# data:image/jpeg;base64,xxx 或 data:image/png;base64,xxx
_DATA_URL_RE = re.compile(r"^data:image/(\w+);base64,(.+)$", re.I)


def _decode_data_url(url: str) -> tuple[bytes, str] | None:
    """解析 data:image/xxx;base64,... 返回 (bytes, 扩展名) 或 None。"""
    if not url or not isinstance(url, str):
        return None
    m = _DATA_URL_RE.match(url.strip())
    if not m:
        return None
    ext, b64 = m.group(1).lower(), m.group(2)
    if ext == "jpeg":
        ext = "jpg"
    try:
        raw = base64.b64decode(b64)
    except Exception:
        return None
    return (raw, ext)


def _get_image_bytes_from_part(part: Any) -> tuple[bytes, str] | None:
    """从单条 content part 中取出图片字节与扩展名，不支持则返回 None。"""
    if not isinstance(part, dict):
        return None
    # image_url: { "url": "data:image/...;base64,..." 或 "https://..." }
    if "image_url" in part:
        url = part["image_url"]
        if isinstance(url, dict) and url.get("url"):
            url = url["url"]
        if isinstance(url, str) and url.strip().lower().startswith("data:image/"):
            return _decode_data_url(url)
        return None  # 不拉取 http(s) URL
    # Gemini inlineData
    if "inlineData" in part:
        data = part["inlineData"]
        if not isinstance(data, dict):
            return None
        b64 = data.get("data")
        mime = (data.get("mimeType") or "").strip().lower()
        if not b64:
            return None
        try:
            raw = base64.b64decode(b64)
        except Exception:
            return None
        ext = "png"
        if "jpeg" in mime or "jpg" in mime:
            ext = "jpg"
        elif "gif" in mime:
            ext = "gif"
        elif "webp" in mime:
            ext = "webp"
        return (raw, ext)
    return None


def extract_image_payloads_from_contexts(
    contexts: list[Any],
    max_messages: int = 6,
) -> list[tuple[bytes, str]]:
    """
    从 contexts 最近 max_messages 条消息中提取内联图片（仅 base64/data URL），返回 [(bytes, ext), ...]。
    不拉取远程 URL；扩展名用于 Hindsight 识别类型（jpg/png/gif/webp）。
    """
    if not contexts or max_messages <= 0:
        return []
    payloads: list[tuple[bytes, str]] = []
    seen_hashes: set[int] = set()  # 同轮内简单去重（按前 1k 字节 hash）
    for ctx in contexts[-max_messages:]:
        content = ctx.get("content")
        if not content:
            continue
        if isinstance(content, str):
            continue
        if not isinstance(content, list):
            continue
        for part in content:
            out = _get_image_bytes_from_part(part)
            if not out:
                continue
            raw, ext = out
            if len(raw) == 0:
                continue
            h = hash(raw[:1024]) if len(raw) >= 1024 else hash(raw)
            if h in seen_hashes:
                continue
            seen_hashes.add(h)
            payloads.append((raw, ext))
    return payloads


def make_image_file_like(image_bytes: bytes, ext: str) -> BytesIO:
    """构造带 .name 的 file-like，便于 multipart 上传。"""
    f = BytesIO(image_bytes)
    f.name = f"image.{ext}"
    return f


def retain_file_if_supported(client: Any, bank_id: str, image_bytes: bytes, ext: str, **kwargs: Any) -> bool:
    """
    若 client 支持 retain_file（同步），则调用并返回 True；否则返回 False。
    kwargs 可传 parser、parser_fallback、context 等（视客户端版本而定）。
    """
    if client is None:
        return False
    method = getattr(client, "retain_file", None)
    if not callable(method):
        return False
    file_like = make_image_file_like(image_bytes, ext)
    try:
        method(bank_id=bank_id, file=file_like, **kwargs)
        return True
    except TypeError:
        try:
            file_like.seek(0)
            method(bank_id=bank_id, file=file_like)
            return True
        except Exception:
            return False
    except Exception:
        return False


async def retain_images_async(
    client: Any,
    bank_id: str,
    payloads: list[tuple[bytes, str]],
    context: str = "astrbot_chat",
    parser: str | None = None,
) -> int:
    """
    异步将多张图片写入 Hindsight（retain_file）。优先 aretain_file，否则 to_thread(retain_file)。
    返回成功写入的图片数量。
    """
    if not client or not payloads:
        return 0
    retain_file = getattr(client, "retain_file", None)
    aretain_file = getattr(client, "aretain_file", None)
    if not callable(retain_file) and not callable(aretain_file):
        return 0
    kwargs: dict[str, Any] = {}
    if context:
        kwargs["context"] = context
    if parser:
        kwargs["parser"] = parser
    done = 0
    for image_bytes, ext in payloads:
        file_like = make_image_file_like(image_bytes, ext)
        try:
            if callable(aretain_file):
                await aretain_file(bank_id=bank_id, file=file_like, **kwargs)
            else:
                await asyncio.to_thread(retain_file, bank_id=bank_id, file=file_like, **kwargs)
            done += 1
        except TypeError:
            try:
                file_like.seek(0)
                if callable(aretain_file):
                    await aretain_file(bank_id=bank_id, file=file_like)
                else:
                    await asyncio.to_thread(retain_file, bank_id=bank_id, file=file_like)
                done += 1
            except Exception:
                pass
        except Exception:
            pass
    return done
