"""OA 通知书结构化解析。"""
from __future__ import annotations

from pk.llm.client import chat_json

PROMPT = """解析以下中国 OA 通知书（审查意见通知书 / 第 N 次审查意见），输出结构化 JSON：
{{
  "case_no": "...",
  "examiner": "...",
  "issue_date": "...",
  "rejected_claims": [整数列表],
  "grounds": [{{"law": "A22.3|A22.2|A26.3|A26.4|A33|R20.2|R34", "summary": "..."}}],
  "cited_documents": [{{"id": "D1", "pub_no": "...", "title": "...", "key_points": "..."}}],
  "examiner_argument": "审查员的核心说理",
  "amendments_required": "建议的修改方向（如有）"
}}

OA 文本：
{oa}
"""


def parse_oa(oa_text: str) -> dict:
    return chat_json(PROMPT.format(oa=oa_text))
