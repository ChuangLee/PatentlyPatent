"""v0.16 spike-B: Agent SDK 单端点 SSE 路由。

POST /api/agent/mine_spike { idea, max_turns? }  -> SSE stream
事件类型：thinking / tool_use / tool_result / delta / done / error
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..agent_sdk_spike import agent_mine_stream

router = APIRouter(prefix="/agent", tags=["agent"])


class MineSpikeRequest(BaseModel):
    idea: str
    max_turns: int = 8


@router.post("/mine_spike")
async def mine_spike(body: MineSpikeRequest):
    async def gen():
        async for ev in agent_mine_stream(body.idea, max_turns=body.max_turns):
            yield {
                "event": ev.get("type", "message"),
                "data": json.dumps(ev, ensure_ascii=False),
            }

    return EventSourceResponse(gen())
