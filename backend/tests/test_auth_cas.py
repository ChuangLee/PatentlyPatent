"""v0.23 CAS auth 单测：用 httpx MockTransport 模拟 CAS server 的 serviceValidate 返回。

跑法：
    cd backend
    PP_MOCK_LLM=1 PP_CAS_ENABLED=1 .venv/bin/pytest tests/test_auth_cas.py -v

不打真 CAS server。
"""
from __future__ import annotations

import os
from urllib.parse import parse_qs, urlparse

# 必须在 import app 之前打开 CAS（config.py 在 module load 时读 env）
os.environ["PP_CAS_ENABLED"] = "1"
os.environ["PP_CAS_SERVER"] = "https://cas.example.test"
os.environ["PP_CAS_SERVICE"] = "https://blind.pub/patent/api/auth/cas/callback"
os.environ["PP_CAS_FRONT_REDIRECT"] = "https://blind.pub/patent/login"

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app import config as _config_mod
from app.config import Settings, settings as _live_settings

# 重新加载 settings 以采纳上面的 env（config.py 在 import 时已实例化一次）
_fresh = Settings()
for k, v in _fresh.model_dump().items():
    setattr(_live_settings, k, v)

from app.main import app  # noqa: E402
from app.routes import auth_cas  # noqa: E402


# ─── XML fixtures ───────────────────────────────────────────────────────────

CAS_SUCCESS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<cas:serviceResponse xmlns:cas='http://www.yale.edu/tp/cas'>
  <cas:authenticationSuccess>
    <cas:user>cas_alice</cas:user>
    <cas:attributes>
      <cas:displayName>爱丽丝（CAS）</cas:displayName>
      <cas:department>研发-CAS 部</cas:department>
    </cas:attributes>
  </cas:authenticationSuccess>
</cas:serviceResponse>
"""

CAS_FAIL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<cas:serviceResponse xmlns:cas='http://www.yale.edu/tp/cas'>
  <cas:authenticationFailure code='INVALID_TICKET'>
    Ticket ST-bad not recognized.
  </cas:authenticationFailure>
</cas:serviceResponse>
"""


# ─── client ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ─── tests ──────────────────────────────────────────────────────────────────

def test_ping_exposes_cas_enabled(client):
    r = client.get("/api/ping")
    assert r.status_code == 200
    assert r.json().get("cas_enabled") is True


def test_cas_login_redirects_to_cas_server(client):
    r = client.get("/api/auth/cas/login", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://cas.example.test/login?service=")
    # service 参数应该被 URL 编码
    assert "blind.pub%2Fpatent%2Fapi%2Fauth%2Fcas%2Fcallback" in loc


def test_cas_callback_success(monkeypatch, client):
    """patch httpx.Client，让 serviceValidate 返成功 XML，断言 callback 跳前端时带 token。"""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "cas.example.test"
        assert "/p3/serviceValidate" in str(request.url.path)
        qs = parse_qs(request.url.query.decode())
        assert qs.get("ticket") == ["ST-good"]
        return httpx.Response(200, text=CAS_SUCCESS_XML)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(auth_cas.httpx, "Client", fake_client)

    r = client.get("/api/auth/cas/callback", params={"ticket": "ST-good"},
                   follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    parsed = urlparse(loc)
    assert parsed.netloc == "blind.pub"
    assert parsed.path == "/patent/login"
    qs = parse_qs(parsed.query)
    assert "token" in qs and qs["token"][0]
    # 解 JWT 验证 sub
    payload = jwt.decode(qs["token"][0], _live_settings.jwt_secret, algorithms=["HS256"])
    assert payload["sub"] == "cas_alice"
    assert payload["role"] == "employee"
    # user payload 应是 JSON
    import json as _json
    user = _json.loads(qs["user"][0])
    assert user["id"] == "cas_alice"
    assert user["name"] == "爱丽丝（CAS）"
    assert user["department"] == "研发-CAS 部"


def test_cas_callback_invalid_ticket(monkeypatch, client):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=CAS_FAIL_XML)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(auth_cas.httpx, "Client", fake_client)

    r = client.get("/api/auth/cas/callback", params={"ticket": "ST-bad"},
                   follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert "cas_error=invalid_ticket" in loc
    assert "token=" not in loc


def test_cas_callback_server_unreachable(monkeypatch, client):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(auth_cas.httpx, "Client", fake_client)

    r = client.get("/api/auth/cas/callback", params={"ticket": "ST-x"},
                   follow_redirects=False)
    assert r.status_code == 302
    assert "cas_error=server_unreachable" in r.headers["location"]


def test_cas_logout_redirects(client):
    r = client.get("/api/auth/cas/logout", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://cas.example.test/logout?service=")
