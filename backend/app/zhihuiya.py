"""智慧芽客户端 — 套餐内端点封装

当前 token 套餐能用：
  - /search/patent/query-search-count
  - /insights/* (10 个端点)
  - /basic-patent-data/(simple-)legal-status

未开通：
  - /search/patent/search（拉文献列表）
  - /basic-patent-data/* （详情/同族/权要/说明书/引用）
"""
from __future__ import annotations
import httpx
from .config import settings


class ZhihuiyaError(RuntimeError):
    pass


async def _post(path: str, json: dict | None = None, params: dict | None = None) -> dict:
    if not settings.use_real_zhihuiya:
        raise ZhihuiyaError("ZHIHUIYA_TOKEN 未配置；后端无法调用智慧芽 API")
    url = settings.zhihuiya_api_base + path
    headers = {"Authorization": f"Bearer {settings.zhihuiya_token}"}
    async with httpx.AsyncClient(timeout=30.0) as cli:
        r = await cli.post(url, headers=headers, json=json or {}, params=params or {})
        r.raise_for_status()
        body = r.json()
        if not body.get("status", True) or body.get("error_code", 0) != 0:
            raise ZhihuiyaError(f"智慧芽业务错误：{body.get('error_code')} {body.get('error_msg')}")
        return body


async def query_search_count(query: str) -> int:
    """任意检索式命中量"""
    body = await _post("/search/patent/query-search-count", json={"query_text": query})
    return int(body.get("data", {}).get("count", 0))


async def patent_trends(query: str, lang: str = "cn") -> dict:
    """专利申请趋势（年）"""
    body = await _post("/insights/patent-trends", json={"query_text": query}, params={"lang": lang})
    return body.get("data", {})


async def applicant_ranking(query: str, lang: str = "cn", n: int = 10) -> list[dict]:
    body = await _post("/insights/applicant-ranking",
                       json={"query_text": query, "limit": n},
                       params={"lang": lang})
    return body.get("data", {}).get("ranking", [])


async def simple_legal_status(patent_number: str) -> dict:
    body = await _post("/basic-patent-data/simple-legal-status",
                       json={"patent_number": patent_number})
    return body.get("data", {})
