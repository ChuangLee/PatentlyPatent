"""文件树 CRUD（与前端 store 行为一致）"""
from __future__ import annotations
import mimetypes
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import FileNode, Project
from ..schemas import FileCreate, FileNodeOut, FileUpdate

router = APIRouter(prefix="/projects/{pid}/files", tags=["files"])

UPLOAD_BASE_URL = "local-upload://"


def _storage_path(pid: str, fid: str, name: str) -> Path:
    return settings.storage_root / "uploads" / pid / fid / name


def _infer_mime(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


@router.get("", response_model=list[dict])
def list_files(pid: str, db: Session = Depends(get_db)):
    if not db.get(Project, pid):
        raise HTTPException(404, "project not found")
    rows = db.query(FileNode).filter(FileNode.project_id == pid).all()
    return [FileNodeOut.model_validate(f).model_dump(by_alias=True) for f in rows]


def _is_readonly_ancestor(db: Session, pid: str, parent_id: str | None) -> bool:
    """v0.37: 向上查 parent，命中任一 readonly=True 节点即视为只读子树。"""
    seen: set[str] = set()
    cur = parent_id
    while cur and cur not in seen:
        seen.add(cur)
        node = db.get(FileNode, cur)
        if node is None or node.project_id != pid:
            return False
        if node.readonly:
            return True
        cur = node.parent_id
    return False


@router.post("", response_model=dict, status_code=201)
def create_file(pid: str, body: FileCreate, db: Session = Depends(get_db)):
    if not db.get(Project, pid):
        raise HTTPException(404, "project not found")
    # v0.37: 拒绝在 readonly 树下创建
    if _is_readonly_ancestor(db, pid, body.parentId):
        raise HTTPException(403, "目标文件夹只读，不能新建文件")
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
    # v0.37: readonly 节点或其祖先 readonly → 拒改
    if f.readonly or _is_readonly_ancestor(db, pid, f.parent_id):
        raise HTTPException(403, "该文件/文件夹只读，不能修改")
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
    # v0.37: readonly 节点或其祖先 readonly → 拒删
    if f.readonly or _is_readonly_ancestor(db, pid, f.parent_id):
        raise HTTPException(403, "该文件/文件夹只读，不能删除")
    # 递归删
    to_del = [fid]
    while to_del:
        cur = to_del.pop()
        node = db.get(FileNode, cur)
        if not node:
            continue
        kids = db.query(FileNode).filter(FileNode.project_id == pid, FileNode.parent_id == cur).all()
        to_del.extend(k.id for k in kids)
        # v0.32: 同时清磁盘 binary
        if (node.url or "").startswith(UPLOAD_BASE_URL):
            try:
                p = _storage_path(pid, node.id, node.name)
                if p.exists():
                    p.unlink()
                    parent = p.parent
                    if parent.exists() and not any(parent.iterdir()):
                        parent.rmdir()
            except OSError:
                pass
        db.delete(node)
    db.commit()


# v0.32: multipart 上传 binary（PDF / office / 图片 等）→ 落到 storage/uploads/<pid>/<fid>/
@router.post("/upload", response_model=dict, status_code=201)
async def upload_file(
    pid: str,
    file: UploadFile = File(...),
    parentId: str | None = Form(default=None),
    source: str = Form(default="user"),
    db: Session = Depends(get_db),
):
    if not db.get(Project, pid):
        raise HTTPException(404, "project not found")
    if not file.filename:
        raise HTTPException(400, "filename required")
    # v0.37: 拒绝上传到 readonly 子树
    if _is_readonly_ancestor(db, pid, parentId):
        raise HTTPException(403, "目标文件夹只读，不能上传")

    fid = f"f-{uuid.uuid4().hex[:10]}"
    target = _storage_path(pid, fid, file.filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with open(target, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)
            size += len(chunk)

    mime = file.content_type or _infer_mime(file.filename)
    node = FileNode(
        id=fid, project_id=pid,
        name=file.filename, kind="file",
        parent_id=parentId, source=source,
        mime=mime, content=None,
        url=f"{UPLOAD_BASE_URL}{pid}/{fid}",
        size=size,
        hidden=False,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return FileNodeOut.model_validate(node).model_dump(by_alias=True)


# v0.32: 下载 / 预览（pdf 浏览器 inline，其他可下载）
@router.get("/{fid}/download")
def download_file(pid: str, fid: str, db: Session = Depends(get_db)):
    f = db.get(FileNode, fid)
    if not f or f.project_id != pid:
        raise HTTPException(404, "file not found")
    # 1) 用户上传的二进制：storage/uploads/{pid}/{fid}/{name}
    if (f.url or "").startswith(UPLOAD_BASE_URL):
        p = _storage_path(pid, fid, f.name)
        if not p.exists():
            raise HTTPException(404, "binary missing on disk")
        mime = f.mime or _infer_mime(f.name)
        return FileResponse(p, media_type=mime, headers={
            "Content-Disposition": f"inline; filename*=utf-8''{quote(f.name)}",
        })
    # 2) agent / 系统生成的二进制：storage/{pid}/{fid}.{ext}（disclosure 生成的 docx 等）
    ext = Path(f.name).suffix or ".bin"
    candidate = settings.storage_root / pid / f"{fid}{ext}"
    if candidate.exists():
        mime = f.mime or _infer_mime(f.name)
        return FileResponse(candidate, media_type=mime, headers={
            "Content-Disposition": f"inline; filename*=utf-8''{quote(f.name)}",
        })
    # 3) 文本类（content 字段）
    if f.content is not None:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(f.content, media_type=f.mime or "text/plain")
    raise HTTPException(404, "no binary stored (legacy file metadata only)")
