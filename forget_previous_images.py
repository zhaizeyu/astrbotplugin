"""
在发给大模型前，将「历史轮次」中的图片替换为占位符，仅保留当前轮的图片。
用于解决多轮对话中 base64 图片导致 token 爆炸、或希望模型“忘记”旧图的问题。
用法：在 main.py 的 on_req_llm 开头调用 forget_previous_images_in_contexts(req)。
"""

from __future__ import annotations

from typing import Any


# 占位符，可配置
IMAGE_PLACEHOLDER = "[图片]"


def _content_has_image(content: Any) -> bool:
    if not content:
        return False
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                if part.get("type") in ("image_url", "image") or "image_url" in part or "inlineData" in part:
                    return True
            elif hasattr(part, "type") and getattr(part, "type", None) in ("image_url", "image"):
                return True
    return False


def _replace_image_parts_with_placeholder(content: Any) -> Any:
    """把 content 里的图片部分替换为占位符文本，保留结构。"""
    if not content:
        return content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        new_parts = []
        for part in content:
            if isinstance(part, dict):
                t = part.get("type")
                if t == "text" and "text" in part:
                    new_parts.append(part)
                elif t in ("image_url", "image") or "image_url" in part or part.get("inlineData"):
                    new_parts.append({"type": "text", "text": IMAGE_PLACEHOLDER})
                else:
                    new_parts.append(part)
            elif hasattr(part, "type"):
                if getattr(part, "type", None) in ("image_url", "image"):
                    new_parts.append({"type": "text", "text": IMAGE_PLACEHOLDER})
                else:
                    new_parts.append(part)
            else:
                new_parts.append(part)
        return new_parts
    return content


def forget_previous_images_in_contexts(
    req: Any,
    keep_last_user_image: bool = True,
) -> None:
    """
    原地修改 req.contexts：将历史消息中的图片替换为占位符，仅保留「最后一轮用户消息」中的图片（可选）。

    :param req: ProviderRequest，需有 req.contexts (list[dict])
    :param keep_last_user_image: True 时保留最后一个 user 消息里的图片；False 时全部替换
    """
    contexts = getattr(req, "contexts", None)
    if not isinstance(contexts, list) or not contexts:
        return

    # 找到「最后一个带 content 的 user 消息」的下标（视为当前轮）
    last_user_idx = -1
    for i in range(len(contexts) - 1, -1, -1):
        ctx = contexts[i]
        if (ctx.get("role") or "").strip().lower() == "user" and ctx.get("content") is not None:
            last_user_idx = i
            break

    for i, ctx in enumerate(contexts):
        content = ctx.get("content")
        if not _content_has_image(content):
            continue
        # 若是“当前轮”用户消息且选择保留，则跳过
        if keep_last_user_image and i == last_user_idx:
            continue
        # 否则替换该条消息中的图片为占位符
        ctx["content"] = _replace_image_parts_with_placeholder(content)
