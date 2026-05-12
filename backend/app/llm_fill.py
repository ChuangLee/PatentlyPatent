"""LLM 注入位填充 — 把 mining.py 模板里的 <!-- [LLM_INJECT::tag::hint] --> 标记替换为实际内容。

走 claude-agent-sdk → claude CLI（OAuth），失败直接抛异常，无 mock fallback。

接口：
  fill_section(content, ctx) -> str
"""
from __future__ import annotations

import re

from .config import settings

INJECT_RE = re.compile(r"<!-- \[LLM_INJECT::([^:]+)::([^\]]+)\] -->")


async def fill_section(content: str, ctx: dict) -> str:
    """统一入口：让 LLM 一次性把所有占位填好，保留 markdown 结构。"""
    if not INJECT_RE.search(content):
        return content

    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        TextBlock,
        query,
    )

    sys_prompt = (
        "你是企业内部专利挖掘助手。下面是一段 markdown 模板，含若干 "
        "<!-- [LLM_INJECT::tag::hint] --> 标记。请：\n"
        "1) 把每个标记原位替换为 hint 要求的内容（中文，简洁专业）；\n"
        "2) 不修改其它 markdown 结构、不添加额外章节、不删除现有标题/表头；\n"
        "3) 表格单元格内填短文本（≤30 字）；\n"
        "4) 列表项 bullet 形式；\n"
        "5) 直接返回最终 markdown，不要解释。"
    )
    proj_ctx = (
        f"项目标题：{ctx.get('title')}\n"
        f"领域：{ctx.get('customDomain') or ctx.get('domain')}\n"
        f"用户报门描述：{ctx.get('description')}\n"
        f"阶段：{(ctx.get('intake') or {}).get('stage', 'idea')}"
    )
    user_msg = f"=== 项目上下文 ===\n{proj_ctx}\n\n=== 模板 ===\n{content}"

    options = ClaudeAgentOptions(
        system_prompt=sys_prompt,
        model=settings.anthropic_model,
        tools=[],   # 禁所有内置工具
        max_turns=5,
    )

    parts: list[str] = []
    try:
        async for msg in query(prompt=user_msg, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        parts.append(block.text)
    except Exception as e:  # noqa: BLE001
        parts.append(f"\n\n_[填充失败：{type(e).__name__}: {e}]_\n")
    return "".join(parts)
