"""文件树 CRUD（与前端 store 行为一致）"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import FileNode, Project
from ..schemas import FileCreate, FileNodeOut, FileUpdate

router = APIRouter(prefix="/projects/{pid}/files", tags=["files"])


@router.get("", response_model=list[dict])
def list_files(pid: str, db: Session = Depends(get_db)):
    if not db.get(Project, pid):
        raise HTTPException(404, "project not found")
    rows = db.query(FileNode).filter(FileNode.project_id == pid).all()
    return [FileNodeOut.model_validate(f).model_dump(by_alias=True) for f in rows]


@router.post("", response_model=dict, status_code=201)
def create_file(pid: str, body: FileCreate, db: Session = Depends(get_db)):
    if not db.get(Project, pid):
        raise HTTPException(404, "project not found")
    fid = f"f-{uuid.uuid4().hex[:10]}"
    f = FileNode(
        id=fid, project_id=pid,
        name=body.name, kind=body.kind,
        parent_id=body.parentId, source=body.source,
        mime=body.mime, content=body.content, url=body.url,
        size=body.size or (len(body.content.encode()) if body.content else None),
        hidden=bool(body.hidden),
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return FileNodeOut.model_validate(f).model_dump(by_alias=True)


@router.patch("/{fid}", response_model=dict)
def update_file(pid: str, fid: str, body: FileUpdate, db: Session = Depends(get_db)):
    f = db.get(FileNode, fid)
    if not f or f.project_id != pid:
        raise HTTPException(404, "file not found")
    if body.name is not None: f.name = body.name
    if body.parentId is not None: f.parent_id = body.parentId
    if body.content is not None:
        f.content = body.content
        f.size = len(body.content.encode())
    if body.hidden is not None: f.hidden = body.hidden
    f.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(f)
    return FileNodeOut.model_validate(f).model_dump(by_alias=True)


@router.delete("/{fid}", status_code=204)
def delete_file(pid: str, fid: str, db: Session = Depends(get_db)):
    f = db.get(FileNode, fid)
    if not f or f.project_id != pid:
        raise HTTPException(404, "file not found")
    # 递归删
    to_del = [fid]
    while to_del:
        cur = to_del.pop()
        node = db.get(FileNode, cur)
        if not node:
            continue
        kids = db.query(FileNode).filter(FileNode.project_id == pid, FileNode.parent_id == cur).all()
        to_del.extend(k.id for k in kids)
        db.delete(node)
    db.commit()
