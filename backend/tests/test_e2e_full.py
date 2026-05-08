"""v0.21 e2e: 报门 → mine_full → fileTree 校验 → docx 导出。

跑法：
    cd backend
    PP_MOCK_LLM=1 .venv/bin/pytest tests/test_e2e_full.py -v

通过 conftest.py 改 PP_DB_URL 到 tmp，PP_MOCK_LLM=1 走纯 mock，**不会**打真 LLM。
"""
from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

# 来自 conftest 已经设置 PP_DB_URL / PP_MOCK_LLM
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        # v0.21 引入了 JWT auth；TestClient 用老 X-User-Id 兼容路径
        c.headers.update({"X-User-Id": "u1"})
        yield c


def _create_project(client: TestClient) -> str:
    body = {
        "title": "区块链供应链溯源测试",
        "description": "基于联盟链 + 零知识证明做跨企业溯源（pytest e2e）",
        "domain": "infosec",
        "ownerId": "u1",
        "intake": {"stage": "prototype", "goal": "full_disclosure", "notes": "e2e"},
    }
    resp = client.post("/api/projects", json=body)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "id" in data and data["id"].startswith("p-")
    # 创建后默认带 3 个根文件夹
    names = [n["name"] for n in data.get("fileTree", []) if n.get("parentId") is None]
    assert "AI 输出" in names
    assert ".ai-internal" in names
    return data["id"]


def _parse_sse(stream_text: str) -> list[dict]:
    """把 sse_starlette 的文本 stream 拆成 (event, data_json) 列表。"""
    events = []
    block: list[str] = []
    for line in stream_text.splitlines():
        if line == "":
            if block:
                ev = {"event": None, "data": ""}
                for ln in block:
                    if ln.startswith("event: "):
                        ev["event"] = ln[len("event: "):]
                    elif ln.startswith("data: "):
                        ev["data"] += ln[len("data: "):]
                events.append(ev)
                block = []
        else:
            block.append(line)
    if block:
        ev = {"event": None, "data": ""}
        for ln in block:
            if ln.startswith("event: "):
                ev["event"] = ln[len("event: "):]
            elif ln.startswith("data: "):
                ev["data"] += ln[len("data: "):]
        events.append(ev)
    return events


def test_e2e_full_pipeline(client: TestClient):
    # ── 1) 报门 ──
    pid = _create_project(client)

    # ── 2) mine_full SSE ──
    mine_body = {"idea": "用零知识证明压缩跨链溯源数据，提升吞吐到 5000 tps"}
    with client.stream(
        "POST", f"/api/agent/mine_full/{pid}", json=mine_body,
        headers={"Accept": "text/event-stream"},
    ) as resp:
        assert resp.status_code == 200, resp.read()
        assert "text/event-stream" in resp.headers.get("content-type", "")
        text = b"".join(resp.iter_bytes()).decode("utf-8", errors="replace")

    events = _parse_sse(text)
    assert len(events) > 0, "no SSE events"

    section_done = [e for e in events if e["event"] == "section_done"]
    done = [e for e in events if e["event"] == "done"]
    section_starts = [e for e in events if e["event"] == "section_start"]

    # 至少 5 个 section_done
    assert len(section_done) >= 5, (
        f"expected >=5 section_done, got {len(section_done)}; "
        f"starts={len(section_starts)} events_total={len(events)}"
    )
    # 至少 1 个 done
    assert len(done) >= 1, f"no terminal done event; events={[e['event'] for e in events][-5:]}"
    # done 含 sections_completed
    done_data = json.loads(done[-1]["data"])
    assert done_data.get("type") == "done"
    assert isinstance(done_data.get("sections_completed"), list)
    assert len(done_data["sections_completed"]) >= 5

    # ── 3) GET project 校验 fileTree 含 .ai-internal/_compare/full/ 下 5 个 md ──
    proj = client.get(f"/api/projects/{pid}").json()
    tree = proj.get("fileTree") or []
    by_id = {n["id"]: n for n in tree}
    # 找到 _compare 文件夹
    full_folders = [n for n in tree if n["name"] == "full" and n["kind"] == "folder"]
    assert len(full_folders) == 1, f"_compare/full folder not found; tree names={[n['name'] for n in tree]}"
    full_id = full_folders[0]["id"]
    md_files = [n for n in tree if n.get("parentId") == full_id and n["kind"] == "file"]
    md_names = sorted(n["name"] for n in md_files)
    expected = {
        "prior_art.md", "summary.md", "embodiments.md",
        "claims.md", "drawings_description.md",
    }
    assert expected.issubset(set(md_names)), (
        f"missing md under _compare/full/; got={md_names} expected_subset={expected}"
    )

    # ── 4) 导出 docx（端点路径是 /disclosure/docx，不是 /export）──
    # 注：题目里写的 /disclosure/export 在当前 backend 里不存在；落地的是
    # POST /api/projects/{pid}/disclosure/docx — TODO: 后续若需补 /export 别名，再加。
    resp = client.post(f"/api/projects/{pid}/disclosure/docx")
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload.get("ok") is True
    file_meta = payload.get("file") or {}
    assert file_meta.get("mime", "").startswith(
        "application/vnd.openxmlformats"
    ), f"unexpected mime: {file_meta.get('mime')}"


def test_budget_status_endpoint(client: TestClient):
    resp = client.get("/api/admin/budget_status")
    assert resp.status_code == 200
    data = resp.json()
    for k in ("daily_sum", "warn_threshold", "block_threshold", "blocked"):
        assert k in data, f"missing key {k} in {data}"
    # 默认 mock 模式 cost = 0，不该 blocked
    assert data["blocked"] is False
    assert data["warn_threshold"] == pytest.approx(2.0)
    assert data["block_threshold"] == pytest.approx(10.0)


def test_sse_concurrency_limit_returns_503(client: TestClient, monkeypatch):
    """超出 5 路并发应直接 503，而不是排队。"""
    # 把上限调到 0 模拟「全占满」
    from app import concurrency
    monkeypatch.setattr(concurrency, "SSE_MAX_CONCURRENCY", 0)
    # 注：semaphore 仍是 5 槽位但 acquire_sse_slot 用 _in_flight 计数器先比，
    # 0 上限会让所有请求都拒。
    pid = _create_project(client)
    resp = client.post(
        f"/api/agent/mine_full/{pid}",
        json={"idea": "test concurrency limit"},
    )
    assert resp.status_code == 503
    assert "繁忙" in resp.text or "服务繁忙" in resp.text
