"""技术效果矩阵：一手段对应多效果，OA 三步法第二步全靠它。"""
from __future__ import annotations

from pk.llm.client import chat_json

PROMPT = """为每个技术手段挖掘多维技术效果。维度：性能、成本、可靠性、可制造性、能耗、可解释性、安全性、合规性。

输出 JSON：[{{"means": "...", "effects": {{"performance": "...", "cost": "..."}}}}]

技术手段：
{means}
"""


def effect_matrix(means: list[str]) -> list[dict]:
    return chat_json(PROMPT.format(means="\n".join(f"- {m}" for m in means)))
