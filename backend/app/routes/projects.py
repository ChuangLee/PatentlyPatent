"""项目 CRUD + 文件树初始化"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from pydantic import BaseModel

from ..db import get_db
from ..models import Project, FileNode
from ..schemas import ProjectCreate, ProjectOut, FileNodeOut
from .auth import get_current_user, CurrentUser


class ProjectUpdate(BaseModel):
    title: str | None = None
    archived: bool | None = None

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_to_out(p: Project, with_files: bool = False) -> dict:
    out = {
        "id": p.id, "title": p.title, "domain": p.domain,
        "customDomain": p.custom_domain, "description": p.description,
        "status": p.status, "archived": bool(getattr(p, "archived", False) or False),
        "ownerId": p.owner_id,
        "createdAt": p.created_at.isoformat(),
        "updatedAt": p.updated_at.isoformat(),
        "intake": p.intake_json, "miningSummary": p.mining_summary_json,
        "searchReport": p.search_report_json, "disclosure": p.disclosure_json,
        "planSnapshot": p.plan_snapshot_json,
    }
    if with_files:
        out["fileTree"] = [
            FileNodeOut.model_validate(f).model_dump(by_alias=True) for f in p.files
        ]
    return out


@router.get("", response_model=list[dict])
def list_projects(
    ownerId: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    q = select(Project)
    if ownerId:
        q = q.where(Project.owner_id == ownerId)
    rows = db.scalars(q.order_by(Project.updated_at.desc())).all()
    return [_project_to_out(p) for p in rows]


@router.get("/{pid}", response_model=dict)
def get_project(pid: str, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    return _project_to_out(p, with_files=True)


@router.post("", response_model=dict, status_code=201)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    # v0.21：以 JWT 身份覆盖 body.ownerId（防伪造）；老 X-User-Id 兼容路径同样适用
    if not body.ownerId:
        body.ownerId = current.id
    pid = f"p-{uuid.uuid4().hex[:8]}"
    p = Project(
        id=pid,
        title=body.title,
        domain=body.domain,
        custom_domain=body.customDomain,
        description=body.description,
        status="drafting",
        owner_id=body.ownerId,
        intake_json=body.intake.model_dump() if body.intake else None,
    )
    db.add(p)

    # 默认 3 根文件夹
    now = datetime.now(timezone.utc)
    for fid, name, source, hidden in [
        ("root-user-" + pid,    "我的资料",    "user",   False),
        ("root-ai-" + pid,      "AI 输出",     "ai",     False),
        ("root-internal-" + pid,".ai-internal", "system", True),
    ]:
        db.add(FileNode(
            id=fid, project_id=pid, name=name, kind="folder",
            parent_id=None, source=source, hidden=hidden,
            created_at=now, updated_at=now,
        ))

    # v0.37: 报门文字自动落地到「我的资料/0-报门.md」让员工随手能看，agent 也能 read_user_file
    intake_dict = body.intake.model_dump() if body.intake else None
    stage_label = {"idea": "创意阶段", "prototype": "已有原型", "deployed": "已落地"}.get(
        (intake_dict or {}).get("stage", ""), "—",
    )
    goal_label = {
        "search_only": "仅检索",
        "full_disclosure": "完整交底书",
        "specific_section": "特定章节",
    }.get((intake_dict or {}).get("goal", ""), "—")
    intake_notes = (intake_dict or {}).get("notes", "") or "—"
    intake_md = (
        f"# 报门：{body.title}\n\n"
        f"> 由系统自动落地，员工可随手翻看；AI 也能 read_user_file 读到。\n\n"
        f"## 基本信息\n\n"
        f"- **项目标题**：{body.title}\n"
        f"- **技术领域**：{body.customDomain or body.domain}\n"
        f"- **当前阶段**：{stage_label}\n"
        f"- **本次目标**：{goal_label}\n"
        f"- **报门时间**：{now.isoformat(timespec='seconds')}\n\n"
        f"## 创意描述\n\n{body.description}\n\n"
        + (f"## 补充说明\n\n{intake_notes}\n" if intake_notes != "—" else "")
    )
    db.add(FileNode(
        id=f"f-intake-{pid}",
        project_id=pid,
        name="0-报门.md",
        kind="file",
        parent_id="root-user-" + pid,
        source="user",
        mime="text/markdown",
        content=intake_md,
        size=len(intake_md.encode("utf-8")),
        readonly=False,    # 用户可以改，但通常不需要
        created_at=now,
        updated_at=now,
    ))

    # 上传的 attachments → 我的资料/
    if body.attachments:
        for a in body.attachments:
            mime = a.mime
            if a.type == "link":
                mime = "text/x-link"
            elif a.type == "note":
                mime = "text/markdown"
            db.add(FileNode(
                id=f"f-{uuid.uuid4().hex[:10]}",
                project_id=pid,
                name=a.name + (".md" if a.type == "note" else ""),
                kind="file",
                parent_id="root-user-" + pid,
                source="user",
                mime=mime,
                size=a.size,
                content=a.content,
                url=a.url,
            ))

    # v0.37: 建第 4 个根"本系统文档"（只读，含 PRD/HLD/使用说明）
    from ..system_docs import ensure_system_docs
    ensure_system_docs(db, pid)

    db.commit()
    db.refresh(p)
    return _project_to_out(p, with_files=True)


@router.patch("/{pid}", response_model=dict)
def update_project(pid: str, body: ProjectUpdate, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    if body.title is not None:
        p.title = body.title
    if body.archived is not None:
        p.archived = body.archived
    db.commit()
    db.refresh(p)
    return _project_to_out(p)


@router.delete("/{pid}", status_code=204)
def delete_project(pid: str, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    db.delete(p)  # cascade delete files (relationship cascade='all, delete-orphan')
    db.commit()
    return None
