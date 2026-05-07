"""v0.2 挖掘模块测试。"""
from __future__ import annotations

from pk.pipeline import run_mine


def test_mine_returns_three_blocks(sample_inventions):
    out = run_mine(sample_inventions["system"])
    assert "problem_tree" in out
    assert "effects" in out
    assert "portfolio" in out
