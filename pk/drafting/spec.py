"""说明书五段骨架（技术领域/背景/发明内容/附图说明/具体实施方式）。"""
from __future__ import annotations

from typing import Any

from pk.llm.client import chat_json

SYSTEM = "你是中国资深专利代理师。说明书撰写恪守 A26.3 充分公开。"

PROMPT = """基于权利要求与交底，生成说明书五段骨架。每段 200-500 字，输出 JSON：
{{
  "technical_field": "...",
  "background": "...（只写现有技术做了什么+缺陷，不贬损过度）",
  "summary": "...（与权要一一对应，每独权配技术效果段）",
  "drawings": "...（附图说明，列出图1/图2..及对应内容）",
  "embodiments": "...（≥1 完整实施例 + 变形例 + 参数范围端点和优选值，确保 A26.3 充分公开）"
}}

权利要求：
{claims}

交底：
{invention}
"""


def generate_spec_skeleton(invention: str, claims: list[str], prior_art: dict[str, Any] | None = None) -> dict[str, str]:
    return chat_json(PROMPT.format(claims="\n".join(claims[:8]), invention=invention), system=SYSTEM)
