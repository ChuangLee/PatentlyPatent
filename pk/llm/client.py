"""Anthropic Claude client with prompt caching.

Default model: claude-opus-4-7 (撰写/答辩)。
Light tasks (lint/extract): claude-sonnet-4-6 — 通过 model 参数切换。

Env:
  ANTHROPIC_API_KEY  必填
  PK_MODEL           默认模型（可选）
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

DEFAULT_MODEL = os.environ.get("PK_MODEL", "claude-opus-4-7")
LIGHT_MODEL = os.environ.get("PK_LIGHT_MODEL", "claude-sonnet-4-6")


OFFLINE = os.environ.get("PK_OFFLINE_DEMO") == "1" or not os.environ.get("ANTHROPIC_API_KEY")


def _client():
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("anthropic SDK 未安装：pip install anthropic") from e
    return anthropic.Anthropic()


_OFFLINE_FIXTURES = {
    "extract_elements": {
        "field": ["专利全流程辅助系统", "AI/NLP", "知识图谱"],
        "problem": ["代理师效率低", "撰写质量参差", "OA 答辩耗时"],
        "means": ["LLM 多 agent 编排", "法条嵌入式 lint", "关键字检索 + 多源聚合"],
        "effect": ["提速 5-10 倍", "降低 A33/A26 风险", "标准化产出"],
    },
    "expand_keywords": {
        "LLM": {"syn": ["大语言模型"], "broader": ["神经网络"], "narrower": ["GPT", "Claude"], "en": ["large language model"]},
    },
    "compare_one": {
        "problem_match": "部分相同",
        "means_match": "本申请采用法条嵌入式 lint，对比文件未涉及",
        "effect_match": "效果相近但本申请有 R20.2 lint 差异",
        "x_or_y": "Y",
        "summary": "可能与其他文献结合用于创造性评价",
    },
    "lint_empty": [],
}


def _offline_chat(prompt: str) -> str:
    p = prompt[:300]
    if "至少 5 项从属权利要求" in p:
        return ("2. 根据权利要求 1 所述的方法，其特征在于，所述法条 lint 包括 R20.2 必要技术特征校验。\n"
                "3. 根据权利要求 1 或 2 所述的方法，其特征在于，多源检索包含 CNIPA、Google Patents 至少之一。\n"
                "4. 根据权利要求 1 所述的方法，其特征在于，关键字扩展包括同义词、上位词、下位词、英文译名。\n"
                "5. 根据权利要求 1 所述的方法，其特征在于，独立权利要求生成包含强、中、弱三档候选。\n"
                "6. 根据权利要求 5 所述的方法，其特征在于，每档候选附带概括度风险标注。")
    if "档不同概括度" in p:
        return ("[强] 一种基于大语言模型的专利全流程辅助系统，包括：检索模块、撰写模块、体检模块。<概括度风险>: 上位过激，可能被对比文件破新颖性。\n\n"
                "[中] 一种基于大语言模型的专利全流程辅助方法，包括：要素拆解步骤；多源关键字检索步骤；基于法条 lint 的体检步骤；其特征在于法条 lint 包含 R20.2/A26 规则。<概括度风险>: 稳妥。\n\n"
                "[弱] 如中档但限定使用 Claude opus-4-7 + Google Patents + CNIPA 双源。<概括度风险>: 紧贴实施例，确定性高。")
    return ""


def _offline_chat_json(prompt: str):
    p = prompt[:300]
    if "拆成四要素" in p:
        return _OFFLINE_FIXTURES["extract_elements"]
    if "扩展同义词" in p:
        return _OFFLINE_FIXTURES["expand_keywords"]
    if "破新颖性(X)" in p:
        return _OFFLINE_FIXTURES["compare_one"]
    if "构建" in p and "问题树" in p:
        return {
            "problem_tree": [
                {"why": 1, "question": "为什么需要本方案？", "answer": "现有技术效率低", "children": []},
            ],
            "what_if": [{"scenario": "对手少做一步", "evasion_point": "改用等效手段 X"}],
            "effects": {"performance": "+30%", "cost": "-20%", "reliability": "+", "energy": "-",
                        "manufacturability": "+", "other": []},
        }
    if "上位—中位—下位" in p:
        return {"feature": {"broad": "...", "mid": "...", "narrow": "...", "risk": "mid", "rationale": "..."}}
    if "为每个技术手段挖掘多维技术效果" in p:
        return [{"means": "示例手段", "effects": {"performance": "+", "cost": "-"}}]
    if "专利布局草图" in p:
        return {"core_product": {"summary": "...", "claim_seed": "..."}, "core_method": {},
                "application": {}, "peripheral": [], "improvement": [], "defensive_publication": []}
    if "结构化 JSON" in p and "OA" in p:
        return {"case_no": "TEST", "examiner": "", "issue_date": "",
                "rejected_claims": [1], "grounds": [{"law": "A22.3", "summary": "示例"}],
                "cited_documents": [], "examiner_argument": "", "amendments_required": ""}
    if "amendments" in p and "anchor" in p:
        return {"amendments": []}
    if "说明书五段骨架" in p:
        return {
            "technical_field": "本发明涉及专利全流程自动化辅助领域。",
            "background": "现有专利撰写主要依赖代理师人工，效率有限；现有商业 AI 系统多为模板填充，缺少法条嵌入式判断。",
            "summary": "本发明提供一种基于 LLM 的专利全流程辅助系统/方法，通过四要素拆解、多源关键字检索、法条 lint 实现高质量产出。",
            "drawings": "图 1 为系统总体架构；图 2 为检索流程；图 3 为撰写流程。",
            "embodiments": "实施例 1：以中文交底输入，调用 elements 模块拆分四要素，参数 max_results=20…（详见说明书）。",
        }
    return _OFFLINE_FIXTURES["lint_empty"]


def chat(prompt: str, *, model: str = DEFAULT_MODEL, system: str | None = None,
         max_tokens: int = 4096, cache_system: bool = True) -> str:
    """Single-turn chat. Caches system prompt for reuse across calls."""
    if OFFLINE:
        return _offline_chat(prompt)
    cli = _client()
    system_blocks = []
    if system:
        block = {"type": "text", "text": system}
        if cache_system:
            block["cache_control"] = {"type": "ephemeral"}
        system_blocks.append(block)
    msg = cli.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_blocks if system_blocks else None,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")


def chat_json(prompt: str, *, model: str = LIGHT_MODEL, system: str | None = None) -> Any:
    """Chat expecting JSON output. Strips markdown fences if present."""
    if OFFLINE:
        return _offline_chat_json(prompt)
    raw = chat(prompt, model=model, system=system)
    raw = raw.strip()
    m = re.search(r"\{.*\}|\[.*\]", raw, re.DOTALL)
    if not m:
        raise ValueError(f"LLM 未返回 JSON：{raw[:200]}")
    return json.loads(m.group(0))
