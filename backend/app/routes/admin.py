"""v0.19-D: admin observability 端点。

GET /api/admin/agent_runs?limit=50  — 最近 N 条 AgentRunLog
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AgentRunLog

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/agent_runs")
def list_agent_runs(limit: int = 50, db: Session = Depends(get_db)):
    limit = max(1, min(int(limit or 50), 500))
    rows = db.scalars(
        select(AgentRunLog)
        .order_by(AgentRunLog.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "endpoint": r.endpoint,
            "project_id": r.project_id,
            "idea": r.idea,
            "num_turns": r.num_turns,
            "total_cost_usd": r.total_cost_usd,
            "duration_ms": r.duration_ms,
            "stop_reason": r.stop_reason,
            "fallback_used": r.fallback_used,
            "error": r.error,
            "is_mock": r.is_mock,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
