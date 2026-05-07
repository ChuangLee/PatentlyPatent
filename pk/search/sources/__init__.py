"""Source dispatcher."""
from __future__ import annotations

from typing import Any

from pk.search.sources.base import SourceBase
from pk.search.sources.cnipa import CnipaSource
from pk.search.sources.googlepatents import GooglePatentsSource
from pk.search.sources.epo_ops import EpoOpsSource
from pk.search.sources.uspto_odp import UsptoOdpSource

REGISTRY: dict[str, type[SourceBase]] = {
    "cnipa": CnipaSource,
    "googlepatents": GooglePatentsSource,
    "epo": EpoOpsSource,
    "uspto": UsptoOdpSource,
}


def dispatch_sources(queries: dict[str, list[str]], sources: list[str], max_results: int = 20) -> list[dict[str, Any]]:
    """Run keyword search on selected sources, merge & deduplicate hits."""
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    primary_q = queries.get("mid", queries.get("tight", [""]))[0]
    for name in sources:
        cls = REGISTRY.get(name.strip())
        if not cls:
            continue
        try:
            src_hits = cls().search(primary_q, max_results=max_results)
        except Exception as e:
            src_hits = [{"error": f"{name}: {e}"}]
        for h in src_hits:
            key = h.get("doc_id") or h.get("title", "") or ""
            if key in seen:
                continue
            seen.add(key)
            hits.append({**h, "source": name})
    return hits
