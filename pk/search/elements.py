"""四要素拆解：技术领域 / 技术问题 / 技术手段 / 技术效果。

MVP: 直接调用 LLM 输出结构化 JSON。后续可加规则后处理。
"""
from __future__ import annotations

from pk.llm.client import chat_json

PROMPT = """你是资深中国专利代理师。把以下交底/草稿/关键词拆成四要素，输出 JSON：
{{
  "field": [3-5 个技术领域/应用对象关键词，含上下位],
  "problem": [3-5 个要解决的技术问题表述],
  "means": [3-5 个核心技术手段及其同义/上下位],
  "effect": [3-5 个技术效果，含性能/成本/可靠性等多维]
}}

只输出 JSON，不要解释。

输入：
{text}
"""


def extract_elements(text: str) -> dict[str, list[str]]:
    return chat_json(PROMPT.format(text=text))
