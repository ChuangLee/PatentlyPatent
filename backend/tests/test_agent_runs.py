"""v0.34: detached agent runs — start → events 落 DB → status completed。

跑法：
    cd backend
    PP_MOCK_LLM=1 .venv/bin/pytest tests/test_agent_runs.py -v
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        c.headers.update({"X-User-Id": "u1"})
        yield c


def _wait_terminal(client: TestClient, run_id: str, timeout_s: float = 30.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        r = client.get(f"/api/agent/runs/{run_id}")
        assert r.status_code == 200, r.text
        data = r.json()
        if data["status"] != "running":
            return data
        time.sleep(0.2)
    pytest.fail(f"run {run_id} did not finish in {timeout_s}s")


def test_start_mine_spike_run_persists_events(client: TestClient):
    # 1) start
    r = client.post(
        "/api/agent/runs/start",
        json={"endpoint": "mine_spike", "idea": "测试 detached run", "max_turns": 4},
    )
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    assert run_id.startswith("r-")

    # 2) 立即 GET status 应该是 running 或 completed
    info = client.get(f"/api/agent/runs/{run_id}").json()
    assert info["id"] == run_id
    assert info["endpoint"] == "mine_spike"

    # 3) 等终态
    final = _wait_terminal(client, run_id)
    assert final["status"] in ("completed", "error"), f"unexpected: {final}"

    # 4) events 至少有 5 条（mock 路径有 thinking + 多个 tool_use/tool_result + delta + done）
    evs = client.get(f"/api/agent/runs/{run_id}/events").json()
    assert isinstance(evs, list)
    assert len(evs) >= 5, f"expected >=5 events, got {len(evs)}"
    types = {e["type"] for e in evs}
    assert "done" in types or "error" in types
    # seq 递增
    seqs = [e["seq"] for e in evs]
    assert seqs == sorted(seqs)


def test_active_run_lookup(client: TestClient):
    # 创建项目以挂 project_id
    pr = client.post(
        "/api/projects",
        json={
            "title": "active run 测试",
            "description": "用于验证 active run 查询",
            "domain": "ai",
            "ownerId": "u1",
            "intake": {"stage": "idea", "goal": "full_disclosure"},
        },
    )
    assert pr.status_code == 201, pr.text
    pid = pr.json()["id"]

    r = client.post(
        "/api/agent/runs/start",
        json={"endpoint": "mine_spike", "project_id": pid, "idea": "active 查询 case"},
    )
    assert r.status_code == 200
    run_id = r.json()["run_id"]

    # 立即查 active：可能 running 也可能已完成（mock 极快）
    a = client.get(f"/api/agent/runs/active?project_id={pid}").json()
    if a is not None:
        assert a["id"] == run_id
        assert a["status"] == "running"

    _wait_terminal(client, run_id)
    # 终态后 active 应为 None
    a2 = client.get(f"/api/agent/runs/active?project_id={pid}").json()
    assert a2 is None


def test_events_since_param(client: TestClient):
    r = client.post(
        "/api/agent/runs/start",
        json={"endpoint": "mine_spike", "idea": "since 参数 case"},
    )
    run_id = r.json()["run_id"]
    _wait_terminal(client, run_id)

    all_evs = client.get(f"/api/agent/runs/{run_id}/events").json()
    assert len(all_evs) >= 3
    mid = all_evs[1]["seq"]
    tail = client.get(f"/api/agent/runs/{run_id}/events?since={mid}").json()
    assert all(e["seq"] > mid for e in tail)
    assert len(tail) == len(all_evs) - 2
