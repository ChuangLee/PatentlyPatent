"""USPTO Open Data Portal (ODP) REST adapter — keyword search.

Docs: https://data.uspto.gov/  (legacy PatentsView is being retired by 2026-03-20)
Auth: USPTO_ODP_KEY env (X-API-Key header).

Note: ODP API surface evolves; we use /api/v1/patent/applications search-style endpoint
with query params. If the real endpoint shape differs in your tenancy, adjust _build_url.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from pk.search.sources.base import SourceBase

ODP_BASE = "https://api.uspto.gov"


class UsptoOdpSource(SourceBase):
    name = "uspto"

    def __init__(self) -> None:
        self.key = os.environ.get("USPTO_ODP_KEY")

    def search(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        if not self.key:
            return [{"warning": "USPTO_ODP_KEY 未设置，跳过 USPTO 检索", "doc_id": "", "title": "", "abstract": ""}]
        with httpx.Client(timeout=30.0) as cli:
            r = cli.get(f"{ODP_BASE}/api/v1/patent/applications/search",
                        params={"q": query, "limit": max_results},
                        headers={"X-API-Key": self.key, "Accept": "application/json"})
            r.raise_for_status()
            data = r.json()
        return self._parse(data, max_results)

    @staticmethod
    def _parse(payload: dict, limit: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in (payload.get("results") or payload.get("patents") or [])[:limit]:
            out.append({
                "doc_id": str(item.get("patentNumber") or item.get("applicationNumberText", "")),
                "title": item.get("inventionTitle") or item.get("title", ""),
                "abstract": item.get("abstractText") or item.get("abstract", ""),
                "applicant": item.get("applicantName") or "",
                "pub_date": item.get("publicationDate") or item.get("filingDate", ""),
                "url": item.get("url", ""),
            })
        return out
