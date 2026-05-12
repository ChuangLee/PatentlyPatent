"""LLM 客户端：统一走 claude-agent-sdk → claude CLI 子进程（OAuth）。

所有 LLM 调用走同一条路径，凭证用 `~/.claude/.credentials.json`。
不再依赖 ANTHROPIC_API_KEY，不再有 mock fallback —— CLI 不可用直接抛错。
"""
from __future__ import annotations

from typing import AsyncIterator

from .config import settings


async def stream_chat(
    user_msg: str,
    *,
    system: str = "你是企业内部的专利挖掘助手，回答简洁、专业。",
    model: str | None = None,
) -> AsyncIterator[str]:
    """流式产出文本片段（chunks）。失败直接抛异常。"""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        TextBlock,
        query,
    )

    # 关键：tools=[] 禁用所有内置工具（allowed_tools 不是禁用，是免授权清单）；
    # max_turns=5 给一点余量。无工具的纯对话模型不应该需要多轮。
    options = ClaudeAgentOptions(
        system_prompt=system,
        model=model or settings.anthropic_model,
        tools=[],
        max_turns=5,
    )

    try:
        async for msg in query(prompt=user_msg, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        yield block.text
    except Exception as e:  # noqa: BLE001
        # 不让 SDK 异常炸 SSE 流；把错误吐给上层当一段普通文本，再让 caller 正常 done
        yield f"\n\n[抱歉，调用 LLM 失败：{type(e).__name__}: {e}]"


def split_grapheme(text: str, size: int = 3) -> list[str]:
    """把字符串按 grapheme 切成片段，用于伪流式（与前端 utils/sse 格式一致）"""
    out: list[str] = []
    for i in range(0, len(text), size):
        out.append(text[i : i + size])
    return out
