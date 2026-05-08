"""v0.23：CAS protocol 2.0/3.0 SSO 接入（与 JWT 共存）

标准 CAS 流程：
  1. 浏览器访问 GET /api/auth/cas/login → 302 到 ${CAS_SERVER}/login?service=${callback}
  2. 用户在 CAS server 完成登录，CAS 重定向回 callback?ticket=ST-xxx
  3. 后端 GET /api/auth/cas/callback 调 ${CAS_SERVER}/serviceValidate?service=...&ticket=...
  4. CAS 返 XML，含 <cas:user>username</cas:user>（可选还有 <cas:attributes>）
  5. 后端解 XML → 查/建用户 → 发 JWT → 302 跳前端 /login?token=...&user=...
  6. 前端接到 ?token=... 后存 store + 跳 dashboard

环境变量：
  PP_CAS_ENABLED=1                      # 默认 false；为 true 时前端 Login.vue 显示 CAS 按钮
  PP_CAS_SERVER=https://cas.example.com # CAS server 根（不带 /login）
  PP_CAS_SERVICE=https://blind.pub/patent/api/auth/cas/callback  # 后端 callback 全 URL
  PP_CAS_FRONT_REDIRECT=https://blind.pub/patent/login           # 前端登录页全 URL

错误处理：
  CAS server 不可达 → 跳前端 /login?cas_error=server_unreachable
  ticket 无效        → 跳前端 /login?cas_error=invalid_ticket
"""
from __future__ import annotations

import json
import logging
from typing import Optional
from urllib.parse import quote, urlencode

import httpx
from defusedxml import ElementTree as DefusedET
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import User
from .auth import _encode_token

log = logging.getLogger("patentlypatent.cas")

router = APIRouter(prefix="/auth/cas", tags=["auth-cas"])

# CAS XML namespaces (CAS 2.0/3.0)
_CAS_NS = "{http://www.yale.edu/tp/cas}"


# ─── helpers ────────────────────────────────────────────────────────────────


def _build_cas_login_url() -> str:
    base = settings.cas_server_url.rstrip("/")
    service = quote(settings.cas_service_url, safe="")
    return f"{base}/login?service={service}"


def _build_cas_validate_url(ticket: str) -> str:
    base = settings.cas_server_url.rstrip("/")
    qs = urlencode({"service": settings.cas_service_url, "ticket": ticket})
    # CAS 3.0 用 /p3/serviceValidate；CAS 2.0 用 /serviceValidate；都尝试 p3 兼容性更好
    return f"{base}/p3/serviceValidate?{qs}"


def _build_front_redirect(token: Optional[str] = None,
                          user_payload: Optional[dict] = None,
                          cas_error: Optional[str] = None) -> str:
    base = settings.cas_frontend_redirect
    parts: list[str] = []
    if token:
        parts.append(f"token={quote(token, safe='')}")
    if user_payload:
        parts.append(f"user={quote(json.dumps(user_payload, ensure_ascii=False), safe='')}")
    if cas_error:
        parts.append(f"cas_error={quote(cas_error, safe='')}")
    sep = "&" if "?" in base else "?"
    return base + (sep + "&".join(parts) if parts else "")


def _parse_cas_xml(xml_text: str) -> tuple[Optional[str], dict]:
    """解 CAS serviceValidate 返回的 XML，拿 (username, attributes_dict)。
    失败返 (None, {})。
    """
    try:
        root = DefusedET.fromstring(xml_text)
    except Exception as e:  # pragma: no cover - 防御性
        log.warning("cas xml parse failed: %s | text=%s", e, xml_text[:300])
        return None, {}

    # 成功节点：<cas:authenticationSuccess><cas:user>...</cas:user></...>
    success = root.find(f"{_CAS_NS}authenticationSuccess")
    if success is None:
        return None, {}
    user_el = success.find(f"{_CAS_NS}user")
    if user_el is None or not (user_el.text or "").strip():
        return None, {}
    username = user_el.text.strip()

    attrs: dict = {}
    attrs_el = success.find(f"{_CAS_NS}attributes")
    if attrs_el is not None:
        for child in list(attrs_el):
            tag = child.tag.replace(_CAS_NS, "")
            attrs[tag] = (child.text or "").strip()
    return username, attrs


def _get_or_create_user(db: Session, username: str, attrs: dict) -> User:
    """username 优先当 user.id；不存在则按 employee 自动创建。"""
    u = db.get(User, username)
    if u:
        return u
    name = attrs.get("displayName") or attrs.get("name") or username
    department = attrs.get("department") or "CAS 接入"
    u = User(id=username, name=name, role="employee", department=department, avatar=None)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ─── routes ─────────────────────────────────────────────────────────────────


@router.get("/login")
def cas_login():
    """302 跳 CAS server login 页（带 service= 回调地址）。"""
    if not settings.cas_enabled:
        raise HTTPException(503, "CAS not enabled (set PP_CAS_ENABLED=1)")
    return RedirectResponse(url=_build_cas_login_url(), status_code=302)


@router.get("/callback")
def cas_callback(ticket: str = Query(...), db: Session = Depends(get_db)):
    """CAS server 回调：验 ticket → 发 JWT → 跳前端。"""
    if not settings.cas_enabled:
        raise HTTPException(503, "CAS not enabled")

    validate_url = _build_cas_validate_url(ticket)
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(validate_url)
    except httpx.HTTPError as e:
        log.error("cas validate request failed: %s", e)
        return RedirectResponse(
            url=_build_front_redirect(cas_error="server_unreachable"),
            status_code=302,
        )

    if resp.status_code != 200:
        log.warning("cas validate non-200: %s | body=%s", resp.status_code, resp.text[:300])
        return RedirectResponse(
            url=_build_front_redirect(cas_error="server_unreachable"),
            status_code=302,
        )

    username, attrs = _parse_cas_xml(resp.text)
    if not username:
        log.info("cas ticket invalid; xml=%s", resp.text[:300])
        return RedirectResponse(
            url=_build_front_redirect(cas_error="invalid_ticket"),
            status_code=302,
        )

    user = _get_or_create_user(db, username, attrs)
    token = _encode_token(user.id, user.role)
    user_payload = {
        "id": user.id,
        "name": user.name,
        "role": user.role,
        "department": user.department,
        "avatar": user.avatar,
    }
    return RedirectResponse(
        url=_build_front_redirect(token=token, user_payload=user_payload),
        status_code=302,
    )


@router.get("/logout")
def cas_logout():
    """跳 CAS server 注销页；前端在跳前应自行清 localStorage token。"""
    if not settings.cas_enabled:
        raise HTTPException(503, "CAS not enabled")
    base = settings.cas_server_url.rstrip("/")
    service = quote(settings.cas_frontend_redirect, safe="")
    return RedirectResponse(url=f"{base}/logout?service={service}", status_code=302)
