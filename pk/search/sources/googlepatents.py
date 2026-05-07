"""Google Patents 关键字检索（HTML 抓取）。

Google Patents 提供免登录的 q= 查询。MVP 用 httpx 抓 HTML + 解析。
注意：尊重 robots.txt + 限速。
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from pk.search.sources.base import SourceBase

UA = "Mozilla/5.0 (compatible; patent_king/0.1)"


class GooglePatentsSource(SourceBase):
    name = "googlepatents"
    base = "https://patents.google.com"

    def search(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        url = f"{self.base}/?q={quote(query)}&num={max_results}"
        with httpx.Client(timeout=30.0, headers={"User-Agent": UA}, follow_redirects=True) as cli:
            r = cli.get(url)
            r.raise_for_status()
            html = r.text
        return self._parse(html, max_results=max_results)

    def _parse(self, html: str, max_results: int) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        hits: list[dict[str, Any]] = []
        for art in soup.select("article")[:max_results]:
            num_el = art.select_one("h4") or art.select_one(".number")
            title_el = art.select_one("h3") or art.select_one(".result-title")
            abs_el = art.select_one(".abstract")
            doc_id = (num_el.get_text(strip=True) if num_el else "")
            doc_id = re.sub(r"\s+", "", doc_id)
            hits.append({
                "doc_id": doc_id,
                "title": title_el.get_text(strip=True) if title_el else "",
                "abstract": abs_el.get_text(" ", strip=True) if abs_el else "",
                "url": f"{self.base}/patent/{doc_id}" if doc_id else "",
            })
        return hits
