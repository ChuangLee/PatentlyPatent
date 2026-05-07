"""EPO Open Patent Services REST adapter (keyword via CQL).

Docs: https://developers.epo.org/  ; OPS v3.2
Auth: OAuth2 client_credentials with EPO_OPS_KEY / EPO_OPS_SECRET env.

Free tier: 4 GB / week (non-commercial).
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from pk.search.sources.base import SourceBase

OPS_BASE = "https://ops.epo.org/3.2/rest-services"
OPS_AUTH = "https://ops.epo.org/3.2/auth/accesstoken"


class EpoOpsSource(SourceBase):
    name = "epo"

    def __init__(self) -> None:
        self.key = os.environ.get("EPO_OPS_KEY")
        self.secret = os.environ.get("EPO_OPS_SECRET")
        self._token: str | None = None

    def _authenticate(self, cli: httpx.Client) -> str:
        if self._token:
            return self._token
        if not (self.key and self.secret):
            raise RuntimeError("EPO_OPS_KEY / EPO_OPS_SECRET 未设置")
        r = cli.post(OPS_AUTH, auth=(self.key, self.secret), data={"grant_type": "client_credentials"})
        r.raise_for_status()
        self._token = r.json()["access_token"]
        return self._token

    def search(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        cql = self._to_cql(query)
        with httpx.Client(timeout=30.0) as cli:
            tok = self._authenticate(cli)
            url = f"{OPS_BASE}/published-data/search/biblio"
            r = cli.get(url, params={"q": cql, "Range": f"1-{max_results}"},
                        headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"})
            r.raise_for_status()
            return self._parse(r.json(), max_results)

    @staticmethod
    def _to_cql(query: str) -> str:
        # Map naive AND/OR query to OPS CQL ta=/ti=/ab= heuristic: search title+abstract
        return f"ta={query}" if " " not in query.strip("\"") else f"ta=({query})"

    @staticmethod
    def _parse(payload: dict, limit: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        try:
            results = (payload.get("ops:world-patent-data", {})
                              .get("ops:biblio-search", {})
                              .get("ops:search-result", {})
                              .get("exchange-documents", []))
            if isinstance(results, dict):
                results = [results]
            for item in results[:limit]:
                doc = item.get("exchange-document", {})
                title_block = doc.get("bibliographic-data", {}).get("invention-title")
                if isinstance(title_block, list):
                    title = next((t.get("$", "") for t in title_block if t.get("@lang") == "en"), "")
                elif isinstance(title_block, dict):
                    title = title_block.get("$", "")
                else:
                    title = ""
                abs_block = doc.get("abstract")
                if isinstance(abs_block, list):
                    abstract = " ".join(p.get("$", "") for p in abs_block if isinstance(p, dict))
                elif isinstance(abs_block, dict):
                    abstract = abs_block.get("p", {}).get("$", "") if isinstance(abs_block.get("p"), dict) else ""
                else:
                    abstract = ""
                out.append({
                    "doc_id": doc.get("@doc-number", ""),
                    "title": title,
                    "abstract": abstract,
                    "url": "",
                })
        except Exception:
            pass
        return out
