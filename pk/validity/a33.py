"""A33 修改超范围 lint：修改后文本必须能在原说明书+权要中"直接毫无疑义确定"。

策略：
1) LLM 抽取草稿中所有特征，与原文做特征级匹配
2) 标注"中间概括"风险（同一独权混合多个实施例的特征）
"""
from __future__ import annotations

from typing import Any

from pk.llm.client import chat_json

PROMPT = """按 CN 专利法 A33 修改超范围审查：当前草稿是否包含原申请文本中"无法直接毫无疑义确定"的
新增/修改特征？特别警示"中间概括"（混合多个实施例的部分特征）。

输出 JSON 数组，每项：
{{"severity": "high|mid|low", "rule": "A33", "title": "...", "detail": "原文锚定情况...",
  "suggestion": "..."}}

原申请：
{original}

修改后草稿：
{draft}
"""


def lint_a33(draft: str, original: str) -> list[dict[str, Any]]:
    try:
        return chat_json(PROMPT.format(draft=draft, original=original))
    except Exception as e:
        return [{"severity": "low", "rule": "A33", "title": "lint 调用失败",
                 "detail": str(e), "suggestion": ""}]
