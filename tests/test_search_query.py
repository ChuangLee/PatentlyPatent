"""单元测试：纯逻辑模块（无 LLM/网络）。"""
from __future__ import annotations

from pk.search.query import build_queries


def test_build_queries_grain():
    keywords = {
        "LLM": {"syn": ["大语言模型"], "broader": ["神经网络"], "narrower": ["GPT"], "en": ["large language model"]},
        "checkpoint": {"syn": ["检查点"], "broader": [], "narrower": [], "en": ["checkpoint"]},
    }
    q = build_queries(keywords)
    assert q["tight"][0].count("AND") == 1  # 2 cores → 1 AND
    assert "大语言模型" in q["mid"][0]
    assert "神经网络" in q["loose"][0]


def test_build_queries_empty():
    q = build_queries({})
    assert q["tight"] == [""]
