"""把四要素 + 扩展词组合成各源的查询串（关键字模式）。"""
from __future__ import annotations

from typing import Any


def build_queries(keywords: dict[str, dict[str, list[str]]]) -> dict[str, list[str]]:
    """生成多种召回粒度的查询串：
    - tight: AND 核心关键词
    - mid:   核心 + 同义词 OR
    - loose: 核心 + 同义+上下位 OR
    """
    cores = list(keywords.keys())[:6]
    tight = " AND ".join(f'"{w}"' for w in cores[:3])
    syn_terms = []
    broad_terms = []
    for w, exp in keywords.items():
        syn_terms += exp.get("syn", [])
        broad_terms += exp.get("broader", []) + exp.get("narrower", [])
    mid = tight + (" AND (" + " OR ".join(f'"{s}"' for s in syn_terms[:8]) + ")" if syn_terms else "")
    loose = mid + (" OR (" + " OR ".join(f'"{s}"' for s in broad_terms[:8]) + ")" if broad_terms else "")
    return {"tight": [tight], "mid": [mid], "loose": [loose]}
