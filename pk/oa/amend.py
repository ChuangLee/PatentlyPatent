"""修改方案生成 + A33 原文锚定校验。

心法：A33 雷区——"中间概括"（混合多个实施例的部分特征）几乎必死。只做删/缩，慎做加/改。
"""
from __future__ import annotations

from pk.llm.client import chat_json

PROMPT = """生成针对当前 OA 的权利要求修改方案。每个修改必须能在原说明书+权利要求书"直接毫无疑义确定"，
否则触犯 A33。

输出 JSON：
{{
  "amendments": [
    {{
      "claim_no": <int>,
      "type": "delete|narrow|merge|insert",
      "before": "原文",
      "after": "修改后",
      "anchor": [
        {{"location": "原文位置（说明书段落X / 权要Y / 实施例Z）", "quote": "原文逐字引用"}}
      ],
      "a33_risk": "low|mid|high",
      "intermediate_concretion_warning": true|false,
      "rationale": "为什么这个修改克服了 OA 中的驳回理由"
    }}
  ]
}}

OA 解析：
{oa_parsed}

原申请文本（说明书+权要）：
{original}

当前权利要求：
{current_claims}
"""


def propose_amendments(oa_parsed: dict, original: str, current_claims: str) -> dict:
    return chat_json(PROMPT.format(oa_parsed=oa_parsed, original=original, current_claims=current_claims))
