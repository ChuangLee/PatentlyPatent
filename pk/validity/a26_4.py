"""A26.4 支持 lint：功能性限定/概括是否落在实施例覆盖范围内。"""
from __future__ import annotations

from typing import Any

from pk.llm.client import chat_json

PROMPT = """按 CN 专利法 A26.4 "权利要求应当以说明书为依据" 审查：
- 功能性限定是否有结构对应？
- 上位概括是否有足够实施例支撑？
- 数值范围端点是否在说明书有数据支撑？

输出 JSON 数组，每项：
{{"severity": "high|mid|low", "rule": "A26.4", "title": "...", "detail": "...", "suggestion": "..."}}

draft:
{draft}
"""


def lint_a26_4(draft: str) -> list[dict[str, Any]]:
    try:
        return chat_json(PROMPT.format(draft=draft))
    except Exception as e:
        return [{"severity": "low", "rule": "A26.4", "title": "lint 调用失败",
                 "detail": str(e), "suggestion": ""}]
