"""A26.3 充分公开 lint：每个独权特征是否能在说明书找到实施例支撑。"""
from __future__ import annotations

from typing import Any

from pk.llm.client import chat_json

PROMPT = """按 CN 专利法 A26.3 "充分公开" 审查：草稿中每条权利要求的每个特征，是否能在说明书的
具体实施方式中找到使本领域技术人员"无需创造性劳动即可实施"的支持。

输出 JSON 数组，每项：
{{"severity": "high|mid|low", "rule": "A26.3", "title": "<特征>缺乏实施例支撑",
  "detail": "...", "suggestion": "建议补充..."}}

draft:
{draft}
"""


def lint_a26_3(draft: str) -> list[dict[str, Any]]:
    try:
        return chat_json(PROMPT.format(draft=draft))
    except Exception as e:
        return [{"severity": "low", "rule": "A26.3", "title": "lint 调用失败",
                 "detail": str(e), "suggestion": ""}]
