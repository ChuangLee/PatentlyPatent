"""R34 单一性 lint：多独权之间是否具有相同/相应的"特定技术特征"。"""
from __future__ import annotations

from typing import Any

from pk.llm.client import chat_json

PROMPT = """按 CN 专利法 R34 单一性审查：多个独立权利要求之间是否具备相同或相应的"特定技术特征"
（即对现有技术作出贡献的特征）？

输出 JSON 数组（无问题则空数组），每项：
{{"severity": "high|mid|low", "rule": "R34", "title": "...", "detail": "...", "suggestion": "建议拆分申请或..."}}

draft:
{draft}
"""


def lint_unity(draft: str) -> list[dict[str, Any]]:
    try:
        return chat_json(PROMPT.format(draft=draft))
    except Exception as e:
        return [{"severity": "low", "rule": "R34", "title": "lint 调用失败",
                 "detail": str(e), "suggestion": ""}]
