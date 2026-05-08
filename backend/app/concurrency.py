"""v0.21: 全局 SSE 并发限流。

核心：
- 5 路并发上限（env PP_SSE_MAX_CONCURRENCY 可调）
- 超出立即返 503，**不排队**（避免 SSE 假响应/前端长时间假活）
- 进入/离开打日志，便于 prod 监控

用法（在 SSE 路由顶部）：

    from ..concurrency import acquire_sse_slot, release_sse_slot, SSEBusy

    try:
        await acquire_sse_slot("mine_full")
    except SSEBusy:
        raise HTTPException(503, "服务繁忙，请稍候")

    async def gen():
        try:
            ...
        finally:
            release_sse_slot("mine_full")

    return EventSourceResponse(gen())

或使用 contextmanager 形式：

    async with sse_slot("mine_full"):
        async for ev in stream(): yield ev
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

logger = logging.getLogger(__name__)

# 默认 5 路并发；env PP_SSE_MAX_CONCURRENCY 覆盖
SSE_MAX_CONCURRENCY: int = int(os.environ.get("PP_SSE_MAX_CONCURRENCY", "5"))

# 全局信号量。Semaphore 自身用 acquire/release 阻塞排队；
# 我们改用「立即非阻塞 acquire」+ 计数器，超限直接抛 SSEBusy。
_sem = asyncio.Semaphore(SSE_MAX_CONCURRENCY)
_in_flight: int = 0
_lock = asyncio.Lock()


class SSEBusy(Exception):
    """全局 SSE 并发已满，应返 503。"""


async def acquire_sse_slot(endpoint: str = "?") -> None:
    """非阻塞获取 1 个 SSE slot；满则抛 SSEBusy。"""
    global _in_flight
    async with _lock:
        if _in_flight >= SSE_MAX_CONCURRENCY:
            logger.warning(
                "[sse_sem] REJECT %s in_flight=%d/%d (busy)",
                endpoint, _in_flight, SSE_MAX_CONCURRENCY,
            )
            raise SSEBusy("sse pool full")
        # 同步槽位 + 信号量
        _in_flight += 1
        # 此处 acquire 不会阻塞，因为 _in_flight 与 _sem 同步增减
        await _sem.acquire()
        logger.info(
            "[sse_sem] ENTER %s in_flight=%d/%d",
            endpoint, _in_flight, SSE_MAX_CONCURRENCY,
        )


def release_sse_slot(endpoint: str = "?") -> None:
    """释放 1 个 slot。允许在异常路径里多次调用是 idempotent 的——但调用方应只调一次。"""
    global _in_flight
    if _in_flight <= 0:
        logger.warning("[sse_sem] release called with in_flight=%d (skip)", _in_flight)
        return
    _in_flight -= 1
    try:
        _sem.release()
    except ValueError:
        pass
    logger.info(
        "[sse_sem] EXIT  %s in_flight=%d/%d",
        endpoint, _in_flight, SSE_MAX_CONCURRENCY,
    )


def in_flight_count() -> int:
    return _in_flight


@asynccontextmanager
async def sse_slot(endpoint: str = "?") -> AsyncIterator[None]:
    """async with sse_slot('mine_full'):  ..."""
    await acquire_sse_slot(endpoint)
    try:
        yield
    finally:
        release_sse_slot(endpoint)
