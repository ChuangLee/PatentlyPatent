"""条件性真 SDK 集成测试 — 仅本地手测用，不进 systemd 启动路径。

跑法（在 backend 目录下，激活 .venv）：

    # 没 key 时：会被 skip
    python -m pytest test_agent_sdk_real.py -s -v
    # 或者直接当脚本：
    python test_agent_sdk_real.py

    # 有 key 时（推荐用 .secrets/anthropic.env）：
    set -a && source ../.secrets/anthropic.env && set +a
    python test_agent_sdk_real.py

预期：拿到至少一个 tool_use 事件 + 一个 done 事件。
"""
from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path

# 让 import app.* 能跑
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _has_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


async def _run_once(idea: str = "用区块链做供应链溯源") -> dict:
    """跑一次真 SDK，统计事件类型分布。"""
    from app.agent_sdk_spike import agent_mine_stream
    from app.config import settings

    assert settings.use_real_llm, (
        f"settings.use_real_llm={settings.use_real_llm}，"
        f"has_key={bool(settings.anthropic_api_key)}，无法真测"
    )

    counts: dict[str, int] = {}
    events: list[dict] = []
    async for ev in agent_mine_stream(idea, max_turns=4):
        t = ev.get("type", "?")
        counts[t] = counts.get(t, 0) + 1
        events.append(ev)
        if len(events) > 50:
            break  # 防失控
    return {"counts": counts, "events": events}


def test_real_sdk_smoke():
    """pytest entry：没 key 直接 skip。"""
    if not _has_key():
        try:
            import pytest  # type: ignore
            pytest.skip("no ANTHROPIC_API_KEY")
        except ImportError:
            print("[SKIP] no ANTHROPIC_API_KEY")
            return
    out = asyncio.run(_run_once())
    assert out["counts"].get("done", 0) >= 1, f"no done event: {out['counts']}"
    assert out["counts"].get("tool_use", 0) >= 1 or out["counts"].get("delta", 0) >= 1, (
        f"no tool_use/delta: {out['counts']}"
    )


if __name__ == "__main__":
    if not _has_key():
        print("[SKIP] no ANTHROPIC_API_KEY in env. 复制 .secrets/anthropic.env.example 并填 key 后再跑")
        sys.exit(0)
    out = asyncio.run(_run_once())
    print("event counts:", out["counts"])
    print("first 5 events:")
    for ev in out["events"][:5]:
        print("  ", ev)
