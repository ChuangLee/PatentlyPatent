"""撰写流水线 + lint 测试。"""
from __future__ import annotations

from pk.pipeline import run_check, run_draft


def test_draft_three_tiers(sample_inventions):
    text = sample_inventions["software"]
    draft = run_draft(text, prior_art=None)
    # Three independence-claim candidates expected
    assert "[强]" in draft and "[中]" in draft and "[弱]" in draft
    assert "## 说明书" in draft
    # Five-section spec
    for sec in ("technical_field", "background", "summary", "drawings", "embodiments"):
        assert sec in draft


def test_draft_with_prior_art(sample_inventions):
    text = sample_inventions["mechanical"]
    fake_pa = {"hits": [{"title": "现有铝合金散热片", "abstract": "传统 PVD 散热涂层 ..."}]}
    draft = run_draft(text, prior_art=fake_pa)
    assert "权利要求书" in draft


def test_check_runs_all_lints(sample_inventions):
    text = sample_inventions["chemistry"]
    draft = run_draft(text)
    report = run_check(draft, original=None)
    assert "法条 lint 体检报告" in report


def test_check_with_original_includes_a33(sample_inventions):
    text = sample_inventions["method"]
    draft = run_draft(text)
    report = run_check(draft, original=text)
    assert "法条 lint 体检报告" in report
