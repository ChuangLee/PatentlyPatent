"""seed 数据：2 个 demo user + 在数据库初始化时确保存在"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class _U:
    id: str
    name: str
    role: str
    department: str
    avatar: str | None = None


DEMO_USERS = [
    _U(id="u1", name="张工程师", role="employee", department="研发-AI 平台部"),
    _U(id="u2", name="王管理员", role="admin",    department="IP 总部"),
]


def seed_users(db) -> None:
    from .models import User
    for u in DEMO_USERS:
        if not db.get(User, u.id):
            db.add(User(id=u.id, name=u.name, role=u.role, department=u.department, avatar=u.avatar))
    db.commit()
