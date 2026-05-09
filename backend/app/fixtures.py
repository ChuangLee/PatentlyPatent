"""seed 数据：2 个 demo user + 在数据库初始化时确保存在"""
from __future__ import annotations
from dataclasses import dataclass

import bcrypt


@dataclass
class _U:
    id: str
    name: str
    role: str
    department: str
    username: str
    password: str          # 明文，仅用于初始化时哈希
    avatar: str | None = None


# v0.28: 两个测试用户（账号密码登录）
DEMO_USERS = [
    _U(
        id="u1",
        name="张工程师",
        role="employee",
        department="研发-AI 平台部",
        username="user",
        password="user123",
    ),
    _U(
        id="u2",
        name="王管理员",
        role="admin",
        department="IP 总部",
        username="admin",
        password="admin123",
    ),
]


def _hash(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def seed_users(db) -> None:
    from .models import User
    for u in DEMO_USERS:
        existing = db.get(User, u.id)
        if not existing:
            db.add(User(
                id=u.id, name=u.name, role=u.role,
                department=u.department, avatar=u.avatar,
                username=u.username, password_hash=_hash(u.password),
            ))
        else:
            # 老数据兼容：补齐 username / password_hash
            changed = False
            if not getattr(existing, "username", None):
                existing.username = u.username
                changed = True
            if not getattr(existing, "password_hash", None):
                existing.password_hash = _hash(u.password)
                changed = True
            if changed:
                db.add(existing)
    db.commit()
