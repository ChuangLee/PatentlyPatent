"""Portfolio 布局草图：核心+方法+应用+外围+改进型+防御性公开。"""
from __future__ import annotations

from pk.llm.client import chat_json

PROMPT = """基于交底与挖掘结果，给出专利布局草图。CN 实务铁律：产品/方法/应用三独权以"产品"为主。

输出 JSON：
{{
  "core_product": {{"summary": "...", "claim_seed": "..."}},
  "core_method": {{"summary": "...", "claim_seed": "..."}},
  "application": {{"summary": "...", "claim_seed": "..."}},
  "peripheral": [{{"topic": "...", "claim_seed": "..."}}],
  "improvement": [{{"topic": "...", "claim_seed": "..."}}],
  "defensive_publication": ["不申请但公开的点 1", "..."]
}}

交底：
{text}

挖掘要点：
{insights}
"""


def design_portfolio(text: str, insights: dict) -> dict:
    return chat_json(PROMPT.format(text=text, insights=insights))
