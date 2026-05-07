"""智慧芽客户端 — 套餐内端点封装

API 风格（实测 2026-05）：
  - /search/patent/query-search-count: POST + JSON body
  - /insights/*: **GET + query string**（POST 报 method_not_allowed）
  - /basic-patent-data/(simple-)legal-status: POST + JSON body
"""
from __future__ import annotations
import httpx
from .config import settings


class ZhihuiyaError(RuntimeError):
    pass


async def _request(method: str, path: str, json: dict | None = None, params: dict | None = None) -> dict:
    if not settings.use_real_zhihuiya:
        raise ZhihuiyaError("ZHIHUIYA_TOKEN 未配置；后端无法调用智慧芽 API")
    url = settings.zhihuiya_api_base + path
    headers = {"Authorization": f"Bearer {settings.zhihuiya_token}"}
    async with httpx.AsyncClient(timeout=30.0) as cli:
        if method == "GET":
            r = await cli.get(url, headers=headers, params=params or {})
        else:
            r = await cli.post(url, headers=headers, json=json or {}, params=params or {})
        r.raise_for_status()
        body = r.json()
        if not body.get("status", True) or body.get("error_code", 0) != 0:
            raise ZhihuiyaError(f"智慧芽业务错误：{body.get('error_code')} {body.get('error_msg') or body.get('error_message')}")
        return body


async def query_search_count(query: str) -> int:
    """任意检索式命中量（POST）"""
    body = await _request("POST", "/search/patent/query-search-count", json={"query_text": query})
    return int(body.get("data", {}).get("count", 0))


async def patent_trends(query: str, lang: str = "cn") -> list[dict]:
    """专利申请趋势（年）— GET"""
    body = await _request("GET", "/insights/patent-trends",
                          params={"query_text": query, "lang": lang})
    return body.get("data", []) or []


async def applicant_ranking(query: str, lang: str = "cn", n: int = 10) -> list[dict]:
    """Top 申请人 — GET"""
    body = await _request("GET", "/insights/applicant-ranking",
                          params={"query_text": query, "lang": lang, "limit": n})
    return body.get("data", []) or []


async def inventor_ranking(query: str, lang: str = "cn", n: int = 10) -> list[dict]:
    body = await _request("GET", "/insights/inventor-ranking",
                          params={"query_text": query, "lang": lang, "limit": n})
    return body.get("data", []) or []


async def most_cited(query: str, lang: str = "cn", n: int = 10) -> list[dict]:
    """高被引专利 — GET"""
    body = await _request("GET", "/insights/most-cited-patents",
                          params={"query_text": query, "lang": lang, "limit": n})
    return body.get("data", []) or []


async def simple_legal_status(patent_number: str) -> dict:
    """公开号 → 法律状态 — POST"""
    body = await _request("POST", "/basic-patent-data/simple-legal-status",
                          json={"patent_number": patent_number})
    return body.get("data", {})
