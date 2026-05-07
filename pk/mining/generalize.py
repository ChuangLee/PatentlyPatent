"""上位/下位概括梯度。"""
from __future__ import annotations

from pk.llm.client import chat_json

PROMPT = """对以下技术特征列表，给出"上位—中位—下位"三级概括梯度。心法：独权能撑多大就撑多大，
但不能撑到容易被无效，边界是"现有技术 + 审查员合理质疑"。

输出 JSON：
{{
  "<原特征>": {{
    "broad": "上位（最激进，潜在 X/Y 风险标注）",
    "mid": "中位（稳妥）",
    "narrow": "下位（紧贴实施例）",
    "risk": "high|mid|low",
    "rationale": "..."
  }}
}}

特征：
{features}
"""


def generalize(features: list[str]) -> dict:
    return chat_json(PROMPT.format(features="\n".join(f"- {f}" for f in features)))
