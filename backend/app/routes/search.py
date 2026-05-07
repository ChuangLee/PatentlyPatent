"""检索：现阶段套餐限制下，只做 insights + 命中数（不能拉文献列表）"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException

from ..config import settings
from ..zhihuiya import query_search_count, patent_trends, applicant_ranking, ZhihuiyaError

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/count")
async def count(q: str):
    if not settings.use_real_zhihuiya:
        return {"available": False, "message": "ZHIHUIYA_TOKEN 未配置（mid-fi 模式）"}
    try:
        return {"available": True, "query": q, "count": await query_search_count(q)}
    except ZhihuiyaError as e:
        raise HTTPException(502, str(e))


@router.get("/trends")
async def trends(q: str, lang: str = "cn"):
    if not settings.use_real_zhihuiya:
        return {"available": False}
    try:
        return {"available": True, "data": await patent_trends(q, lang)}
    except ZhihuiyaError as e:
        raise HTTPException(502, str(e))


@router.get("/applicants")
async def applicants(q: str, lang: str = "cn", n: int = 10):
    if not settings.use_real_zhihuiya:
        return {"available": False}
    try:
        return {"available": True, "data": await applicant_ranking(q, lang, n)}
    except ZhihuiyaError as e:
        raise HTTPException(502, str(e))
