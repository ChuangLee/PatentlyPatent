"""Pydantic schemas — 与前端 TS interface 字段一一对应（camelCase via alias）"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_serializer

ROLE = Literal["employee", "admin"]
PROJECT_STATUS = Literal["drafting", "researching", "reporting", "completed"]
DOMAIN = Literal["cryptography", "infosec", "ai", "other"]
PATENTABILITY = Literal["strong", "moderate", "weak", "not_recommended"]
CLAIM_TIER = Literal["broad", "medium", "narrow"]
XYN = Literal["X", "Y", "N"]
FILE_KIND = Literal["folder", "file"]
FILE_SOURCE = Literal["user", "ai", "system"]
PROJECT_STAGE = Literal["idea", "prototype", "deployed"]
PROJECT_GOAL = Literal["search_only", "full_disclosure", "specific_section"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        alias_generator=lambda name: "".join(
            (w if i == 0 else w.capitalize()) for i, w in enumerate(name.split("_"))
        ),
    )


class UserOut(_CamelModel):
    id: str
    name: str
    role: ROLE
    department: str
    avatar: Optional[str] = None


class IntakeAnswers(_CamelModel):
    stage: PROJECT_STAGE
    goal: PROJECT_GOAL
    notes: Optional[str] = None


class FileNodeOut(_CamelModel):
    id: str
    name: str
    kind: FILE_KIND
    parent_id: Optional[str] = None
    source: FILE_SOURCE
    hidden: bool = False
    readonly: bool = False  # v0.37: 不可编辑标志（系统文档根及其子项）
    mime: Optional[str] = None
    size: Optional[int] = None
    content: Optional[str] = None
    url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _ser_dt(self, v: datetime) -> str:
        return v.isoformat()


class AttachmentIn(BaseModel):
    """报门时的附件（旧字段，保兼容；后端转为 FileNode 入'我的资料/'）"""
    id: str
    type: Literal["file", "link", "note"]
    name: str
    size: Optional[int] = None
    mime: Optional[str] = None
    url: Optional[str] = None
    content: Optional[str] = None
    addedAt: str


class ProjectCreate(BaseModel):
    title: str
    description: str
    domain: DOMAIN
    customDomain: Optional[str] = None
    ownerId: str
    intake: Optional[IntakeAnswers] = None
    attachments: Optional[list[AttachmentIn]] = None


class ProjectOut(_CamelModel):
    id: str
    title: str
    domain: DOMAIN
    custom_domain: Optional[str] = None
    description: str
    status: PROJECT_STATUS
    archived: bool = False
    owner_id: str
    created_at: datetime
    updated_at: datetime
    intake: Optional[IntakeAnswers] = None
    mining_summary: Optional[dict[str, Any]] = None
    search_report: Optional[dict[str, Any]] = None
    disclosure: Optional[dict[str, Any]] = None
    file_tree: Optional[list[FileNodeOut]] = None  # 可选：详情时返回

    @field_serializer("created_at", "updated_at")
    def _ser_dt(self, v: datetime) -> str:
        return v.isoformat()


class LoginAsRequest(BaseModel):
    role: ROLE


class FileCreate(BaseModel):
    name: str
    kind: FILE_KIND
    parentId: Optional[str] = None
    source: FILE_SOURCE = "user"
    mime: Optional[str] = None
    content: Optional[str] = None
    url: Optional[str] = None
    size: Optional[int] = None
    hidden: Optional[bool] = False


class FileUpdate(BaseModel):
    name: Optional[str] = None
    parentId: Optional[str] = None
    content: Optional[str] = None
    hidden: Optional[bool] = None


class ChatRequest(BaseModel):
    round: int = 1
    userMsg: str = ""


class AutoMineRequest(BaseModel):
    aiRootId: Optional[str] = None
    title: Optional[str] = None
    domain: Optional[str] = None
    customDomain: Optional[str] = None
    description: Optional[str] = None
    intake: Optional[IntakeAnswers] = None
