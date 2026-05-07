"""5-Why + 1-What-if 问题树。"""
from __future__ import annotations

from pk.llm.client import chat_json

PROMPT = """你是中国资深专利代理师。对以下交底/技术构思，构建"问题树"：
- 用 5-Why 连续追问技术问题的根因
- 在叶节点用 1-What-if 反推规避设计与等效手段
- 同时挖掘技术效果矩阵（性能/成本/可靠性/能耗/可制造性等多维）

输出 JSON：
{{
  "problem_tree": [
    {{"why": 1, "question": "...", "answer": "...", "children": [...]}}
  ],
  "what_if": [
    {{"scenario": "对手少做X会怎样", "evasion_point": "..."}}
  ],
  "effects": {{
    "performance": "...", "cost": "...", "reliability": "...", "energy": "...", "manufacturability": "...", "other": ["..."]
  }}
}}

输入：
{text}
"""


def build_problem_tree(text: str) -> dict:
    return chat_json(PROMPT.format(text=text))
