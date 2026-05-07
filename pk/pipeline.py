"""High-level pipelines composing modules. Stub implementations for MVP skeleton."""
from __future__ import annotations

from typing import Any

from pk.search.elements import extract_elements
from pk.search.expand import expand_keywords
from pk.search.query import build_queries
from pk.search.sources import dispatch_sources
from pk.search.compare import build_comparison_table
from pk.drafting.claims_indep import generate_independent_claims
from pk.drafting.claims_dep import generate_dependent_claims
from pk.drafting.spec import generate_spec_skeleton
from pk.validity import run_all_lints
from pk.mining.problem_tree import build_problem_tree
from pk.mining.effects import effect_matrix
from pk.mining.portfolio import design_portfolio
from pk.oa.parse import parse_oa
from pk.oa.three_step import three_step_response
from pk.oa.amend import propose_amendments
from pk.oa.rhetoric import render_response


def run_search(invention_text: str, sources: list[str], max_results: int = 20) -> dict[str, Any]:
    elements = extract_elements(invention_text)
    keywords = expand_keywords(elements)
    queries = build_queries(keywords)
    hits = dispatch_sources(queries, sources=sources, max_results=max_results)
    comparison = build_comparison_table(hits, elements)
    return {
        "elements": elements,
        "keywords": keywords,
        "queries": queries,
        "hits": hits,
        "comparison": comparison,
    }


def run_draft(invention_text: str, prior_art: dict[str, Any] | None = None) -> str:
    independent = generate_independent_claims(invention_text, prior_art=prior_art)
    dependent = generate_dependent_claims(independent, invention_text)
    spec = generate_spec_skeleton(invention_text, claims=independent + dependent, prior_art=prior_art)
    return _render_draft(independent, dependent, spec)


def run_check(draft_text: str, original: str | None = None) -> str:
    findings = run_all_lints(draft_text, original=original)
    return _render_check_report(findings)


def run_mine(invention_text: str) -> dict[str, Any]:
    tree = build_problem_tree(invention_text)
    nodes = tree.get("problem_tree", []) if isinstance(tree, dict) else []
    means_list = [n.get("answer", "") for n in nodes if isinstance(n, dict)]
    effects = effect_matrix(means_list) if means_list else []
    portfolio = design_portfolio(invention_text, {"problem_tree": tree, "effects": effects})
    return {"problem_tree": tree, "effects": effects, "portfolio": portfolio}


def run_oa(oa_text: str, application: str, original: str, current_claims: str) -> str:
    parsed = parse_oa(oa_text)
    three = three_step_response(parsed, application)
    amendments = propose_amendments(parsed, original, current_claims)
    return render_response(three, amendments)


def _render_draft(indep: list[str], dep: list[str], spec: dict[str, str]) -> str:
    sections = [
        "# 专利申请草稿\n",
        "## 权利要求书\n",
    ]
    for i, c in enumerate(indep, 1):
        sections.append(f"### 独立权利要求（候选 {i}）\n\n{c}\n")
    for c in dep:
        sections.append(f"{c}\n")
    sections.append("\n## 说明书\n")
    for k in ("technical_field", "background", "summary", "drawings", "embodiments"):
        sections.append(f"### {k}\n\n{spec.get(k, '（待生成）')}\n")
    return "\n".join(sections)


def _render_check_report(findings: list[dict[str, Any]]) -> str:
    lines = ["# 法条 lint 体检报告\n"]
    if not findings:
        lines.append("未检出问题。")
        return "\n".join(lines)
    for f in findings:
        lines.append(f"## [{f['severity']}] {f['rule']} — {f['title']}\n")
        lines.append(f"{f['detail']}\n")
        if f.get("suggestion"):
            lines.append(f"**建议**：{f['suggestion']}\n")
    return "\n".join(lines)
