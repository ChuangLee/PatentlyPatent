"""pytest 全局：在 import app 之前把 PP_DB_URL 改成 tmp，避免污染 prod db。

测试不调真 claude CLI；用 autouse fixture monkeypatch 掉 _stream_real_sdk
和 fill_section / stream_chat 这几个 LLM 出口，给固定 fake 事件流。
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator

import pytest

# 必须在 import app.* 之前设置
_TMP_DIR = Path(tempfile.mkdtemp(prefix="pp_test_"))
os.environ.setdefault("PP_DB_URL", f"sqlite:///{_TMP_DIR / 'test.db'}")
os.environ.setdefault("PP_SSE_MAX_CONCURRENCY", "5")
os.environ.setdefault("PP_STORAGE_ROOT", str(_TMP_DIR / "storage"))
# 跳过启动期 claude CLI 校验（测试不需要真 CLI）
os.environ.setdefault("PP_SKIP_CLI_CHECK", "1")


# ─── fake 事件流：模拟 agent_mine_stream / mine_section_via_agent ────────────


async def _fake_real_sdk_mine(idea_text: str, max_turns: int) -> AsyncIterator[dict]:
    """桩 agent_sdk_spike._stream_real_sdk —— 给一个最简但完整的事件流。"""
    yield {"type": "thinking", "text": f"[stub] analyzing: {idea_text[:40]}"}
    yield {
        "type": "tool_use",
        "name": "search_patents",
        "input": {"query": "TAC: (test)"},
        "id": "stub-1",
    }
    yield {"type": "tool_result", "text": "stub: 100 件命中"}
    yield {"type": "delta", "text": "stub agent 输出片段 1。"}
    yield {"type": "delta", "text": "stub agent 输出片段 2。"}
    yield {
        "type": "done",
        "stop_reason": "end_turn",
        "total_cost_usd": 0.0,
        "num_turns": 1,
        "usage": {},
    }


async def _fake_real_sdk_section(
    section: str, idea_text: str, max_turns: int
) -> AsyncIterator[dict]:
    """桩 agent_section_demo._stream_real_sdk —— 每章产出最小可验证 markdown。"""
    yield {"type": "thinking", "text": f"[stub] section={section}"}
    yield {
        "type": "tool_use",
        "name": "search_patents",
        "input": {"query": "TAC: (stub)"},
        "id": f"stub-{section}-1",
    }
    yield {"type": "tool_result", "text": "stub: 50 件命中"}
    md = f"# {section}\n\nstub markdown for section={section}\n\nidea: {idea_text[:50]}\n"
    for i in range(0, len(md), 40):
        yield {"type": "delta", "text": md[i:i + 40]}
    yield {
        "type": "done",
        "stop_reason": "end_turn",
        "total_cost_usd": 0.0,
        "num_turns": 1,
    }


async def _fake_stream_chat(user_msg: str, **_: Any) -> AsyncIterator[str]:
    """桩 llm.stream_chat 防 chat 路由跑测试时打真 CLI。"""
    yield f"[stub chat] {user_msg[:50]}"


async def _fake_fill_section(content: str, ctx: dict) -> str:
    """桩 llm_fill.fill_section 把占位标记原样保留即可。"""
    return content


@pytest.fixture(autouse=True)
def _stub_llm_paths(monkeypatch):
    """所有测试自动桩掉 LLM 出口，避免任何用例不小心打真 CLI。

    桩点选最贴近 SDK 的位置：
      - agent_sdk_spike._stream_real_sdk
      - agent_section_demo._stream_real_sdk
      - llm.stream_chat
      - llm_fill.fill_section
    这样 dispatcher 上层的所有逻辑（AgentRunLog / 预算 / SSE 限流）都能完整跑。
    """
    from app import agent_sdk_spike, agent_section_demo, llm, llm_fill

    monkeypatch.setattr(agent_sdk_spike, "_stream_real_sdk", _fake_real_sdk_mine)
    monkeypatch.setattr(agent_section_demo, "_stream_real_sdk", _fake_real_sdk_section)
    monkeypatch.setattr(llm, "stream_chat", _fake_stream_chat)
    monkeypatch.setattr(llm_fill, "fill_section", _fake_fill_section)
    yield
