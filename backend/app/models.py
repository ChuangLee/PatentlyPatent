"""ORM 模型 — 与前端 types/index.ts 对齐"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, Boolean
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


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    domain: Mapped[str] = mapped_column(String(64))         # 'cryptography' | 'infosec' | 'ai' | 'other'
    custom_domain: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str] = mapped_column(String(4096))
    status: Mapped[str] = mapped_column(String(32), default="drafting")
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
