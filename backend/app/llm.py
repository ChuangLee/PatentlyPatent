"""LLM 客户端：Anthropic SDK 流式 + mock fallback"""
from __future__ import annotations
import asyncio
import random
from typing import AsyncIterator

from .config import settings


async def stream_chat(
    user_msg: str,
    *,
    system: str = "你是企业内部的专利挖掘助手，回答简洁、专业。",
    model: str | None = None,
) -> AsyncIterator[str]:
    """流式产出文本片段（chunks）。"""
    model = model or settings.anthropic_model
    if not settings.use_real_llm:
        async for c in _mock_stream(user_msg):
            yield c
        return
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        async with client.messages.stream(
            model=model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        ) as s:
            async for text in s.text_stream:
                yield text
    except Exception as e:
        yield f"\n[LLM 调用失败：{type(e).__name__}: {e}；已 fallback 到 mock 输出]\n"
        async for c in _mock_stream(user_msg):
            yield c


async def _mock_stream(user_msg: str) -> AsyncIterator[str]:
    """无 key / 无网时的占位流。"""
    text = (
        "（mock 模式）我看到了你的输入。\n\n"
        f"摘要：{user_msg[:80]}{'…' if len(user_msg) > 80 else ''}\n\n"
        "由于当前后端未配置 Anthropic API key 或开启了 PP_MOCK_LLM=1，"
        "返回的是占位文本。设置环境变量 ANTHROPIC_API_KEY 后即可切到真 LLM。\n"
    )
    for i in range(0, len(text), 3):
        yield text[i : i + 3]
        await asyncio.sleep(random.uniform(0.02, 0.05))


def split_grapheme(text: str, size: int = 3) -> list[str]:
    """把字符串按 grapheme 切成片段，用于伪流式（与前端 utils/sse 格式一致）"""
    out: list[str] = []
    for i in range(0, len(text), size):
        out.append(text[i : i + size])
    return out
