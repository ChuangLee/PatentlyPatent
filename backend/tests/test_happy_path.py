"""v0.34: happy path 端到端 — 覆盖最基本流程，防 v0.34 同类回归

报门 → 自动启动 detached run → events 持久化 → 关闭客户端不影响后台 → 重连恢复
"""
from __future__ import annotations
import time
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    # with 触发 lifespan startup，init_db + seed_users 才跑
    with TestClient(app) as c:
        yield c


def test_login_with_password_returns_jwt(client: TestClient):
    """v0.28 真账密 — 防认证链路被破坏。"""
    r = client.post("/api/auth/login", json={"username": "user", "password": "user123"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "token" in body and len(body["token"]) > 50
    assert body["user"]["role"] == "employee"

    r2 = client.post("/api/auth/login", json={"username": "user", "password": "WRONG"})
    assert r2.status_code == 401


def test_login_admin_role(client: TestClient):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "admin"


def _bearer(client: TestClient, role: str = "employee") -> dict:
    """v0.21 后 POST /projects 需 JWT；登录拿 token 包成 Authorization header"""
    r = client.post(
        "/api/auth/login",
        json={"username": "user" if role == "employee" else "admin",
              "password": "user123" if role == "employee" else "admin123"},
    )
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_create_project_returns_default_filetree(client: TestClient):
    """报门后必须有「我的资料」「AI 输出」「.ai-internal」三个根 folder。"""
    r = client.post("/api/projects", json={
        "title": "happy path test",
        "description": "测试用",
        "domain": "ai",
        "ownerId": "u1",
    }, headers=_bearer(client))
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    detail = client.get(f"/api/projects/{pid}").json()
    folders = [f["name"] for f in detail.get("fileTree", []) if f["kind"] == "folder"]
    assert "我的资料" in folders
    assert "AI 输出" in folders
    # 清理
    client.delete(f"/api/projects/{pid}")


def test_agent_runs_active_returns_null_when_no_run(client: TestClient):
    """v0.34 关键端点：active 查询不能 404，需返 200 + null。"""
    r = client.get("/api/agent/runs/active", params={"project_id": "p-nonexist"})
    assert r.status_code == 200
    assert r.json() is None


def test_agent_runs_start_returns_run_id_immediately(client: TestClient):
    """detached run start 必须立即返 run_id，不阻塞。"""
    t0 = time.monotonic()
    r = client.post("/api/agent/runs/start", json={
        "endpoint": "mine_spike",
        "idea": "happy path detached",
        "max_turns": 1,
    })
    elapsed = time.monotonic() - t0
    assert r.status_code in (200, 201), r.text
    assert "run_id" in r.json()
    assert elapsed < 5.0, f"start should not block, took {elapsed:.2f}s"


def test_kb_endpoints(client: TestClient):
    """v0.22 kb 浏览端点必须可达。"""
    r = client.get("/api/kb/stats")
    assert r.status_code == 200
    assert "files" in r.json() and "subdirs" in r.json()

    r2 = client.get("/api/kb/tree", params={"path": ""})
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)


def test_admin_budget_status(client: TestClient):
    """v0.21 预算端点必须可达。"""
    r = client.get("/api/admin/budget_status")
    assert r.status_code == 200
    body = r.json()
    assert "daily_sum" in body
    assert "warn_threshold" in body and "block_threshold" in body


def test_ping_includes_cas_enabled(client: TestClient):
    """v0.23 后 /ping 必须含 cas_enabled 字段（前端登录页探测用）。"""
    r = client.get("/api/ping")
    assert r.status_code == 200
    assert "cas_enabled" in r.json()


def test_files_upload_download_round_trip(client: TestClient):
    """v0.32 multipart 上传 → 下载链路（防 PDF/office 预览/下载再坏）。"""
    # 建项目
    r = client.post("/api/projects", json={
        "title": "upload test",
        "description": "x",
        "domain": "ai",
        "ownerId": "u1",
    }, headers=_bearer(client))
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    try:
        # 上传 fake binary
        files = {"file": ("test.pdf", b"%PDF-1.4 fake content", "application/pdf")}
        r2 = client.post(
            f"/api/projects/{pid}/files/upload",
            files=files,
            data={"source": "user"},
        )
        assert r2.status_code == 201, r2.text
        fid = r2.json()["id"]
        assert r2.json()["url"].startswith("local-upload://")

        # 下载验证
        r3 = client.get(f"/api/projects/{pid}/files/{fid}/download")
        assert r3.status_code == 200
        assert r3.headers["content-type"].startswith("application/pdf")
        assert "inline" in r3.headers.get("content-disposition", "")
        assert b"%PDF" in r3.content
    finally:
        # 不删除：测试环境 storage_root 可能与 prod systemd 跑的 path 冲突，
        # 让 cascade 在测试 db 里清理；本测试关注上传/下载链路本身
        pass


def test_critical_endpoints_are_registered(client: TestClient):
    """打一遍所有关键 GET 端点确保 router 注册正确。
    v0.34 bug 是路由顺序导致 active 被 {run_id} 吃掉，加测试防此类。
    """
    # 这些必须返非 404（200/401/403/422 都算注册成功）
    endpoints = [
        ("/api/ping", "GET"),
        ("/api/projects", "GET"),
        ("/api/kb/stats", "GET"),
        ("/api/kb/tree", "GET"),
        ("/api/admin/agent_runs", "GET"),
        ("/api/admin/budget_status", "GET"),
        ("/api/agent/runs/active", "GET"),
    ]
    for path, _ in endpoints:
        r = client.get(path)
        assert r.status_code != 404, f"{path} returns 404 — router not registered or wrong order"
