"""交底书 .docx 生成 + 下载

POST /api/projects/{pid}/disclosure/docx
    合并 'AI 输出/' 下的 markdown，生成 .docx，落盘到 backend/storage/{pid}/，
    并以 FileNode 形式入库到同一个 'AI 输出/' 文件夹。

GET  /api/projects/{pid}/files/{fid}/download
    把落盘的二进制文件作为 FileResponse 返回，供前端下载。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..disclosure_docx import generate_disclosure_docx
from ..models import FileNode, Project
from ..schemas import FileNodeOut

router = APIRouter(tags=["disclosure"])

DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
DOCX_FILENAME = "专利交底书.docx"


def _ai_root_id(pid: str) -> str:
    return f"root-ai-{pid}"


def _user_root_id(pid: str) -> str:
    return f"root-user-{pid}"


def _project_storage_dir(pid: str) -> Path:
    d = settings.storage_root / pid
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/projects/{pid}/disclosure/docx", response_model=dict)
def generate_docx(pid: str, db: Session = Depends(get_db)):
    project = db.get(Project, pid)
    if not project:
        raise HTTPException(404, "project not found")

    # 1) 找 'AI 输出/' folder
    ai_root = db.get(FileNode, _ai_root_id(pid))
    if not ai_root or ai_root.kind != "folder":
        # 兜底：按 name 找
        ai_root = (
            db.query(FileNode)
            .filter(
                FileNode.project_id == pid,
                FileNode.kind == "folder",
                FileNode.parent_id.is_(None),
                FileNode.name.in_(["AI 输出", "AI输出"]),
            )
            .first()
        )
    if not ai_root:
        raise HTTPException(400, "AI 输出/ folder not found in project file tree")

    # 2) 取该文件夹下 markdown 文件，按 name 排序
    md_files = (
        db.query(FileNode)
        .filter(
            FileNode.project_id == pid,
            FileNode.parent_id == ai_root.id,
            FileNode.kind == "file",
        )
        .order_by(FileNode.name.asc())
        .all()
    )
    md_files = [
        f for f in md_files
        if (f.mime in (None, "text/markdown") or (f.name or "").lower().endswith(".md"))
    ]

    # 3) 取「我的资料/」下用户附件，附到 project 上供模板列出
    user_root = db.get(FileNode, _user_root_id(pid))
    user_attachments: list[FileNode] = []
    if user_root:
        user_attachments = (
            db.query(FileNode)
            .filter(
                FileNode.project_id == pid,
                FileNode.parent_id == user_root.id,
                FileNode.kind == "file",
            )
            .order_by(FileNode.name.asc())
            .all()
        )
    setattr(project, "_user_attachments", user_attachments)

    # 4) 生成 docx bytes
    blob = generate_disclosure_docx(project, md_files)

    # 5) 落盘
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    storage_dir = _project_storage_dir(pid)
    disk_name = f"disclosure_{ts}.docx"
    disk_path = storage_dir / disk_name
    disk_path.write_bytes(blob)

    # 6) 入库 FileNode（如已存在同名 'AI 输出/专利交底书.docx'，覆盖更新）
    fid: str
    existing = (
        db.query(FileNode)
        .filter(
            FileNode.project_id == pid,
            FileNode.parent_id == ai_root.id,
            FileNode.name == DOCX_FILENAME,
        )
        .first()
    )
    if existing:
        existing.size = len(blob)
        existing.mime = DOCX_MIME
        existing.url = f"{settings.api_prefix}/projects/{pid}/files/{existing.id}/download"
        existing.content = None  # 二进制不放 inline
        existing.updated_at = datetime.now(timezone.utc)
        # 保存磁盘路径到 url 的同时，独立记录到 content 不太合适；
        # 方案：把 disk_path 名字编码到 url 后端再回查 storage_dir 中最新文件即可。
        # 这里简单：用一个固定的「最新」副本名，覆盖写。
        latest_path = storage_dir / f"{existing.id}.docx"
        latest_path.write_bytes(blob)
        fid = existing.id
        db.commit()
        db.refresh(existing)
        node_out = existing
    else:
        fid = f"f-{uuid.uuid4().hex[:10]}"
        latest_path = storage_dir / f"{fid}.docx"
        latest_path.write_bytes(blob)
        node = FileNode(
            id=fid,
            project_id=pid,
            name=DOCX_FILENAME,
            kind="file",
            parent_id=ai_root.id,
            source="ai",
            mime=DOCX_MIME,
            size=len(blob),
            content=None,
            url=f"{settings.api_prefix}/projects/{pid}/files/{fid}/download",
            hidden=False,
        )
        db.add(node)
        db.commit()
        db.refresh(node)
        node_out = node

    # 7) 项目状态推进
    if project.status != "completed":
        project.status = "completed"
        project.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(project)

    return {
        "ok": True,
        "file": FileNodeOut.model_validate(node_out).model_dump(by_alias=True),
        "projectStatus": project.status,
    }


@router.get("/projects/{pid}/files/{fid}/download")
def download_file(pid: str, fid: str, db: Session = Depends(get_db)):
    f = db.get(FileNode, fid)
    if not f or f.project_id != pid:
        raise HTTPException(404, "file not found")

    storage_dir = _project_storage_dir(pid)
    # 优先返回与 fid 绑定的最新副本
    candidate = storage_dir / f"{fid}.docx"
    if not candidate.exists():
        # 找 storage_dir 下最新的 disclosure_*.docx 兜底
        disclosures = sorted(
            storage_dir.glob("disclosure_*.docx"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if disclosures:
            candidate = disclosures[0]
        else:
            raise HTTPException(404, "file blob not found on disk")

    return FileResponse(
        candidate,
        media_type=f.mime or "application/octet-stream",
        filename=f.name or candidate.name,
    )
