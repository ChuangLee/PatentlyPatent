"""端到端检索流水线测试（offline mock）。"""
from __future__ import annotations

import json
from pathlib import Path

from pk.pipeline import run_search


def test_search_pipeline_basic(sample_inventions, tmp_path):
    text = sample_inventions["software"]
    # Use cnipa source to avoid network (cnipa is a stub returning a placeholder)
    out = run_search(text, sources=["cnipa"], max_results=5)
    assert "elements" in out
    assert "keywords" in out
    assert "queries" in out
    assert "hits" in out
    assert "comparison" in out
    # Elements should be a dict with the four keys
    assert set(out["elements"].keys()) >= {"field", "problem", "means", "effect"}
    # JSON-serializable
    json.dumps(out, ensure_ascii=False)


def test_search_query_grain(sample_inventions):
    out = run_search(sample_inventions["mechanical"], sources=["cnipa"], max_results=3)
    queries = out["queries"]
    assert "tight" in queries and "mid" in queries and "loose" in queries
    assert all(isinstance(v, list) and len(v) == 1 for v in queries.values())


def test_dispatch_unknown_source(sample_inventions):
    out = run_search(sample_inventions["method"], sources=["does-not-exist"], max_results=3)
    # Should return empty hits without crashing
    assert out["hits"] == []
