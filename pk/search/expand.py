"""关键词扩展：同义词 / 上下位 / 中英对照。"""
from __future__ import annotations

from pk.llm.client import chat_json

PROMPT = """对以下专利检索四要素的每个词，扩展同义词、上位词、下位词、英文译名，输出 JSON：
{{ "<原词>": {{"syn": [...], "broader": [...], "narrower": [...], "en": [...]}} }}
要素：
{elements}
"""


def expand_keywords(elements: dict[str, list[str]]) -> dict[str, dict[str, list[str]]]:
    return chat_json(PROMPT.format(elements=elements))
