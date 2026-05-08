"""智慧芽客户端 — 套餐内端点封装

API 风格（实测 2026-05）：
  - /search/patent/query-search-count: POST + JSON body
  - /insights/*: **GET + query string**（POST 报 method_not_allowed）
  - /basic-patent-data/(simple-)legal-status: POST + JSON body

v0.15-C：增加 TTL=300s 模块级缓存 + 超时/5xx 降级（返回空 payload，不抛 500）。
"""
from __future__ import annotations
import time
import logging
from typing import Any, Callable, Awaitable
import httpx
from .config import settings

logger = logging.getLogger(__name__)


class ZhihuiyaError(RuntimeError):
    pass


# ---- TTL cache (in-process, no extra deps) ------------------------------
_CACHE_TTL = 300.0   # 5 min
_CACHE_MAX = 256
_cache: dict[str, tuple[float, Any]] = {}


def _cache_key(endpoint: str, **kw: Any) -> str:
    """normalize: endpoint + sorted kwargs（query 两端去空格、统一小写无关——保留原文以免误命中）"""
    parts = [endpoint]
    for k in sorted(kw.keys()):
        v = kw[k]
        if isinstance(v, str):
            v = v.strip()
        parts.append(f"{k}={v}")
    return "|".join(parts)


def _cache_get(key: str) -> Any | None:
    hit = _cache.get(key)
    if not hit:
        return None
    ts, payload = hit
    if time.time() - ts >= _CACHE_TTL:
        _cache.pop(key, None)
        return None
    return payload


def _cache_set(key: str, payload: Any) -> None:
    if len(_cache) >= _CACHE_MAX:
        # pop 最旧
        oldest = min(_cache.items(), key=lambda kv: kv[1][0])[0]
        _cache.pop(oldest, None)
    _cache[key] = (time.time(), payload)


# ---- HTTP --------------------------------------------------------------
async def _request(method: str, path: str, json: dict | None = None, params: dict | None = None) -> dict:
    if not settings.use_real_zhihuiya:
        raise ZhihuiyaError("ZHIHUIYA_TOKEN 未配置；后端无法调用智慧芽 API")
    url = settings.zhihuiya_api_base + path
    headers = {"Authorization": f"Bearer {settings.zhihuiya_token}"}
    # v0.15-C: 收紧到 10s（原 30s）以便上层快速降级
    async with httpx.AsyncClient(timeout=10.0) as cli:
        if method == "GET":
            r = await cli.get(url, headers=headers, params=params or {})
        else:
            r = await cli.post(url, headers=headers, json=json or {}, params=params or {})
        r.raise_for_status()
        body = r.json()
        if not body.get("status", True) or body.get("error_code", 0) != 0:
            raise ZhihuiyaError(f"智慧芽业务错误：{body.get('error_code')} {body.get('error_msg') or body.get('error_message')}")
        return body


async def _cached_call(
    cache_key: str,
    fn: Callable[[], Awaitable[Any]],
    fallback: Any,
    label: str,
) -> Any:
    """统一：先查缓存 → 调 API → 失败时降级返回 fallback（不入缓存以便下次重试）"""
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.info("zhihuiya cache hit: %s", label)
        return cached
    try:
        result = await fn()
        _cache_set(cache_key, result)
        return result
    except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadTimeout) as e:
        logger.warning("zhihuiya timeout, degrading to empty payload: %s err=%s", label, e)
        return fallback
    except httpx.HTTPStatusError as e:
        sc = e.response.status_code if e.response is not None else 0
        if sc >= 500:
            logger.warning("zhihuiya 5xx, degrading: %s status=%s", label, sc)
            return fallback
        # 4xx 让上层 ZhihuiyaError 路径走（保留可见性）
        logger.warning("zhihuiya http error: %s status=%s", label, sc)
        return fallback


# ---- public API --------------------------------------------------------
async def query_search_count(query: str) -> int:
    """任意检索式命中量（POST）— 智慧芽返回字段为 total_search_result_count，兼容老 SDK 文档的 count"""
    key = _cache_key("query-search-count", query=query)

    async def _do() -> int:
        body = await _request("POST", "/search/patent/query-search-count", json={"query_text": query})
        data = body.get("data", {}) or {}
        return int(data.get("total_search_result_count", data.get("count", 0)))

    return await _cached_call(key, _do, fallback=0, label=f"count[{query[:60]}]")


async def patent_trends(query: str, lang: str = "cn") -> list[dict]:
    """专利申请趋势（年）— GET"""
    key = _cache_key("patent-trends", query=query, lang=lang)

    async def _do() -> list[dict]:
        body = await _request("GET", "/insights/patent-trends",
                              params={"query_text": query, "lang": lang})
        return body.get("data", []) or []

    return await _cached_call(key, _do, fallback=[], label=f"trends[{query[:60]}]")


async def applicant_ranking(query: str, lang: str = "cn", n: int = 10) -> list[dict]:
    """Top 申请人 — GET"""
    key = _cache_key("applicant-ranking", query=query, lang=lang, n=n)

    async def _do() -> list[dict]:
        body = await _request("GET", "/insights/applicant-ranking",
                              params={"query_text": query, "lang": lang, "limit": n})
        return body.get("data", []) or []

    return await _cached_call(key, _do, fallback=[], label=f"applicants[{query[:60]}]")


async def inventor_ranking(query: str, lang: str = "cn", n: int = 10) -> list[dict]:
    key = _cache_key("inventor-ranking", query=query, lang=lang, n=n)

    async def _do() -> list[dict]:
        body = await _request("GET", "/insights/inventor-ranking",
                              params={"query_text": query, "lang": lang, "limit": n})
        return body.get("data", []) or []

    return await _cached_call(key, _do, fallback=[], label=f"inventors[{query[:60]}]")


async def most_cited(query: str, lang: str = "cn", n: int = 10) -> list[dict]:
    """高被引专利 — GET"""
    key = _cache_key("most-cited", query=query, lang=lang, n=n)

    async def _do() -> list[dict]:
        body = await _request("GET", "/insights/most-cited-patents",
                              params={"query_text": query, "lang": lang, "limit": n})
        return body.get("data", []) or []

    return await _cached_call(key, _do, fallback=[], label=f"most-cited[{query[:60]}]")


async def simple_legal_status(patent_number: str) -> dict:
    """公开号 → 法律状态 — POST"""
    key = _cache_key("simple-legal-status", pn=patent_number)

    async def _do() -> dict:
        body = await _request("POST", "/basic-patent-data/simple-legal-status",
                              json={"patent_number": patent_number})
        return body.get("data", {}) or {}

    return await _cached_call(key, _do, fallback={}, label=f"legal-status[{patent_number}]")
