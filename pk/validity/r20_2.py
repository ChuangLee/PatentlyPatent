"""R20.2 必要技术特征最小集 lint。"""
from __future__ import annotations

from typing import Any

from pk.llm.client import chat_json

PROMPT = """以"中国专利法实施细则 R20.2 必要技术特征"为标准，审查以下独立权利要求是否包含
"解决该技术问题所必需的全部特征，不多不少"。

输出 JSON 数组，每项：
{{"severity": "high|mid|low", "rule": "R20.2", "title": "...", "detail": "...", "suggestion": "..."}}

draft:
{draft}
"""


def lint_r20_2(draft: str) -> list[dict[str, Any]]:
    try:
        return chat_json(PROMPT.format(draft=draft))
    except Exception as e:
        return [{"severity": "low", "rule": "R20.2", "title": "lint 调用失败",
                 "detail": str(e), "suggestion": ""}]
