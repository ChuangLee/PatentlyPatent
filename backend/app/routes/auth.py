"""认证：v0.21 引入 JWT 框架（最小可用版）

兼容性：
  - 旧 POST /api/auth/login-as 路由保留（直接返 user，无 token），原型/MSW 仍可用
  - 新 POST /api/auth/login    返回 {token, user}；token=PyJWT(sub=userId, role, exp)
  - 老 X-User-Id header 路径在 get_current_user dependency 里仍兼容（同时支持 Bearer）
本轮目标是 JWT 框架就绪，不强求真密码（仍按 role/userId 一键发 token）。
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..fixtures import DEMO_USERS
from ..models import User
from ..schemas import LoginAsRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


# ─── Pydantic models ────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    """登录入参，两种模式：
    - v0.28 真账密：传 username + password（推荐）
    - v0.21 fake：传 role + 可选 userId（dev 模式 / fallback；生产前端隐藏）
    """
    username: Optional[str] = None
    password: Optional[str] = None
    userId: Optional[str] = None
    role: Optional[str] = None  # 'employee' | 'admin'


class LoginResponse(BaseModel):
    token: str
    user: UserOut


class CurrentUser(BaseModel):
    id: str
    role: str


# ─── JWT helpers ────────────────────────────────────────────────────────────


def _encode_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


# ─── dependency ─────────────────────────────────────────────────────────────


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> CurrentUser:
    """优先 Bearer JWT，回退老 X-User-Id header（兼容 v0.20 及之前）。"""
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "invalid authorization header")
        try:
            payload = _decode_token(token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "token expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(401, f"invalid token: {e}")
        sub = payload.get("sub")
        role = payload.get("role")
        if not sub:
            raise HTTPException(401, "token missing sub")
        return CurrentUser(id=sub, role=role or "employee")
    # 兼容老路径
    if x_user_id:
        return CurrentUser(id=x_user_id, role="employee")
    raise HTTPException(401, "missing authorization")


# ─── routes ─────────────────────────────────────────────────────────────────


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """v0.28：username + password 真校验；保留 v0.21 role 路径作 dev fallback。"""
    from sqlalchemy import select
    from ..fixtures import verify_password

    user_obj = None

    # 模式 1：账密
    if req.username and req.password:
        u = db.scalar(select(User).where(User.username == req.username))
        if not u or not verify_password(req.password, u.password_hash):
            raise HTTPException(401, "用户名或密码错误")
        user_obj = u

    # 模式 2：role/userId fallback（dev / 兼容老前端）
    if user_obj is None:
        if req.role not in ("employee", "admin"):
            raise HTTPException(400, "请提供 username+password，或 role")
        if req.userId:
            user_obj = db.get(User, req.userId)
        if user_obj is None:
            demo = next((u for u in DEMO_USERS if u.role == req.role), None)
            if not demo:
                raise HTTPException(404, "no demo user for role")
            user_obj = db.get(User, demo.id) or demo

    user_dict = (
        user_obj.__dict__
        if not hasattr(user_obj, "id") or not hasattr(user_obj, "department")
        else {
            "id": user_obj.id,
            "name": user_obj.name,
            "role": user_obj.role,
            "department": user_obj.department,
            "avatar": getattr(user_obj, "avatar", None),
        }
    )
    token = _encode_token(user_dict["id"], user_dict["role"])
    return LoginResponse(token=token, user=UserOut.model_validate(user_dict))


@router.post("/login-as", response_model=UserOut)
def login_as(req: LoginAsRequest):
    """老接口保留，仅返回 user（不带 token），保兼容 MSW + 旧前端代码。"""
    user = next((u for u in DEMO_USERS if u.role == req.role), None)
    if not user:
        raise HTTPException(404, "no demo user for role")
    return UserOut.model_validate(user.__dict__, from_attributes=False)


@router.get("/me", response_model=UserOut)
def me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.get(User, current.id)
    if u:
        return UserOut.model_validate({
            "id": u.id, "name": u.name, "role": u.role,
            "department": u.department, "avatar": u.avatar,
        })
    demo = next((d for d in DEMO_USERS if d.id == current.id), None)
    if demo:
        return UserOut.model_validate(demo.__dict__, from_attributes=False)
    raise HTTPException(404, "user not found")
