"""独立权利要求生成：3 档概括度 (强/中/弱) 供选。

策略来自调研 ai_docs/research_03_cn_practice.md：
- 强档：上位词最激进，独权能撑多大就撑多大
- 中档：保守稳妥，技术特征 7±2
- 弱档：紧贴实施例，确定性最高
"""
from __future__ import annotations

from typing import Any

from pk.llm.client import chat

SYSTEM = """你是中国资深专利代理师，深谙 CNIPA 实务（专利法 A22/A26/R20.2、审查指南 2023）。
撰写独立权利要求时遵守：
- R20.2 必要技术特征最小集：独权只写"解决技术问题所必需的全部特征"，不多不少
- 三段式适用机械/结构；软件/算法/化学用整体式
- 不在权要中写附图标号
- 避免功能性限定无结构对应（A26.4 雷区）
"""

PROMPT = """基于以下交底与现有技术信息，生成 3 档不同概括度的独立权利要求供选择：
- 强：上位最激进，技术特征 5±1，但保证不被对比文件破新颖性
- 中：稳妥，技术特征 7±2
- 弱：紧贴实施例，技术特征 9±2

每档输出独立成段，前缀 [强]/[中]/[弱]，并在每档末尾加一行 "<概括度风险>: ..." 说明潜在风险。

交底：
{invention}

现有技术摘要（如有）：
{prior_art}
"""


def generate_independent_claims(invention: str, prior_art: dict[str, Any] | None = None) -> list[str]:
    pa_summary = ""
    if prior_art and prior_art.get("hits"):
        for h in prior_art["hits"][:5]:
            pa_summary += f"- {h.get('title', '')}: {h.get('abstract', '')[:200]}\n"
    text = chat(PROMPT.format(invention=invention, prior_art=pa_summary or "（无）"), system=SYSTEM)
    parts = []
    cur: list[str] = []
    for line in text.splitlines():
        if line.startswith("[强]") or line.startswith("[中]") or line.startswith("[弱]"):
            if cur:
                parts.append("\n".join(cur).strip())
            cur = [line]
        else:
            cur.append(line)
    if cur:
        parts.append("\n".join(cur).strip())
    return parts or [text]
