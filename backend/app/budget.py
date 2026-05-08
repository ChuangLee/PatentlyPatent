"""v0.21: 当日预算告警与硬阻断。

依赖 AgentRunLog.total_cost_usd 列（v0.19 已存在）。

阈值：
- DAILY_WARN  = 2 USD（env PP_DAILY_BUDGET_WARN）
- DAILY_BLOCK = 10 USD（env PP_DAILY_BUDGET_BLOCK）

行为：
- 写入 AgentRunLog 后调用 update_after_run() 一次：
    - 当日 sum > WARN  → logger.info（已超 warn）
    - 当日 sum > BLOCK → logger.warning（已超 block）
- SSE 端点入口调 ensure_not_blocked()，触发 BLOCK 阈值时抛 BudgetBlocked，
  外层返 503 "今日预算已超限"。

注意：用 daily window = UTC 当日 00:00–23:59。生产里换 settings.tz 可调。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select

from .db import SessionLocal
from .models import AgentRunLog

logger = logging.getLogger(__name__)


DAILY_WARN: float = float(os.environ.get("PP_DAILY_BUDGET_WARN", "2.0"))
DAILY_BLOCK: float = float(os.environ.get("PP_DAILY_BUDGET_BLOCK", "10.0"))


class BudgetBlocked(Exception):
    """当日预算已超 block 阈值；上层应返 503。"""

    def __init__(self, daily_sum: float):
        super().__init__(f"daily budget block exceeded: ${daily_sum:.4f} > ${DAILY_BLOCK:.2f}")
        self.daily_sum = daily_sum


def _utc_today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


def get_daily_sum() -> float:
    """读 AgentRunLog 当日 total_cost_usd 之和（UTC 日）。"""
    start = _utc_today_start()
    end = start + timedelta(days=1)
    db = SessionLocal()
    try:
        s = db.execute(
            select(func.coalesce(func.sum(AgentRunLog.total_cost_usd), 0.0))
            .where(AgentRunLog.created_at >= start)
            .where(AgentRunLog.created_at < end)
        ).scalar_one()
        return float(s or 0.0)
    finally:
        db.close()


def check_daily_budget() -> dict:
    """对外快速查询 — 返 dict（admin 端点用）。"""
    daily = get_daily_sum()
    return {
        "daily_sum": round(daily, 6),
        "warn_threshold": DAILY_WARN,
        "block_threshold": DAILY_BLOCK,
        "warned": daily > DAILY_WARN,
        "blocked": daily > DAILY_BLOCK,
        "window": "UTC-day",
    }


def update_after_run(endpoint: str | None = None) -> dict:
    """每次写入 AgentRunLog 后调一次。日志副作用 + 返当前状态。"""
    state = check_daily_budget()
    daily = state["daily_sum"]
    if state["blocked"]:
        logger.warning(
            "[budget] BLOCK daily=$%.4f > $%.2f endpoint=%s",
            daily, DAILY_BLOCK, endpoint,
        )
    elif state["warned"]:
        logger.info(
            "[budget] WARN  daily=$%.4f > $%.2f endpoint=%s",
            daily, DAILY_WARN, endpoint,
        )
    return state


def ensure_not_blocked() -> None:
    """SSE 入口调用 — 已超 block 直接抛 BudgetBlocked。"""
    daily = get_daily_sum()
    if daily > DAILY_BLOCK:
        raise BudgetBlocked(daily)
