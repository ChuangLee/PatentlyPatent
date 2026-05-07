"""特征对照表 + X/Y 类标注。"""
from __future__ import annotations

from typing import Any

from pk.llm.client import chat_json


def build_comparison_table(hits: list[dict[str, Any]], elements: dict[str, list[str]]) -> list[dict[str, Any]]:
    """对每篇命中文献，输出 {id, title, problem_match, means_match, effect_match, x_or_y, summary}。

    MVP: 让 LLM 基于摘要做判断；正式版需引入特征级别 NLI。
    """
    out = []
    for h in hits:
        prompt = (
            "你是资深代理师。以下是本申请要素与一篇对比文件，判断其是否能破新颖性(X)或与其他文献结合破创造性(Y)，"
            "并按问题/手段/效果对齐。仅输出 JSON。\n"
            f"本申请要素：{elements}\n对比文件：{h.get('title')}\n摘要：{h.get('abstract', '')}\n"
            '{"problem_match": "...", "means_match": "...", "effect_match": "...", "x_or_y": "X|Y|N", "summary": "..."}'
        )
        try:
            judgement = chat_json(prompt)
        except Exception as e:
            judgement = {"error": str(e)}
        out.append({**h, **judgement})
    return out
