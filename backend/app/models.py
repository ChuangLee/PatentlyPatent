"""ORM 模型 — 与前端 types/index.ts 对齐"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, Boolean, Float, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))   # 'employee' | 'admin'
    department: Mapped[str] = mapped_column(String(128))
    avatar: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # v0.28: 账号密码登录（fake auth → 真账密）
    username: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    domain: Mapped[str] = mapped_column(String(64))         # 'cryptography' | 'infosec' | 'ai' | 'other'
    custom_domain: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str] = mapped_column(String(4096))
    status: Mapped[str] = mapped_column(String(32), default="drafting")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    intake_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mining_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    search_report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    disclosure_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    files: Mapped[list["FileNode"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class FileNode(Base):
    __tablename__ = "file_nodes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(16))            # 'folder' | 'file'
    parent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(16))          # 'user' | 'ai' | 'system'
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    mime: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str | None] = mapped_column(String, nullable=True)   # 内联文本（md/txt/json）
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)  # 链接 / 占位下载 URL
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    project: Mapped["Project"] = relationship(back_populates="files")


class AgentRunLog(Base):
    """v0.19: agent 调用 observability 日志表。
    每次跑 agent 入口（mine_spike / ab_compare / prior_art_smart 等）写一行。
    监控失败绝不阻塞业务（写入由调用方 try/except 兜住）。
    """
    __tablename__ = "agent_run_logs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    idea: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    num_turns: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer)
    stop_reason: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
