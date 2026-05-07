"""项目 CRUD + 文件树初始化"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db import get_db
from ..models import Project, FileNode
from ..schemas import ProjectCreate, ProjectOut, FileNodeOut

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_to_out(p: Project, with_files: bool = False) -> dict:
    out = {
        "id": p.id, "title": p.title, "domain": p.domain,
        "customDomain": p.custom_domain, "description": p.description,
        "status": p.status, "ownerId": p.owner_id,
        "createdAt": p.created_at.isoformat(),
        "updatedAt": p.updated_at.isoformat(),
        "intake": p.intake_json, "miningSummary": p.mining_summary_json,
        "searchReport": p.search_report_json, "disclosure": p.disclosure_json,
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
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
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

    db.commit()
    db.refresh(p)
    return _project_to_out(p, with_files=True)
