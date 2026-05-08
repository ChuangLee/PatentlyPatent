"""v0.22: 只读专利知识库浏览（refs/专利专家知识库/）。

每个项目都能看到，懒加载（一层一层），禁止任何写操作。
"""
from __future__ import annotations
import mimetypes
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse

from ..config import PROJECT_ROOT

router = APIRouter(prefix="/kb", tags=["kb"])

KB_ROOT = (PROJECT_ROOT / "refs" / "专利专家知识库").resolve()
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5MB


def _safe_path(rel: str) -> Path:
    """把相对路径解析到 KB_ROOT 内，防 .."""
    rel = (rel or "").strip().lstrip("/")
    full = (KB_ROOT / rel).resolve() if rel else KB_ROOT
    if not str(full).startswith(str(KB_ROOT)):
        raise HTTPException(400, "invalid path (escapes kb root)")
    if not full.exists():
        raise HTTPException(404, f"not found: {rel}")
    return full


def _infer_mime(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".md") or lower.endswith(".markdown"):
        return "text/markdown"
    if lower.endswith(".txt"):
        return "text/plain"
    if lower.endswith(".json"):
        return "application/json"
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".html") or lower.endswith(".htm"):
        return "text/html"
    if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
        return mimetypes.guess_type(name)[0] or "image/*"
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


@router.get("/tree", response_model=list[dict])
def list_kb_dir(path: str = Query(default="")):
    """一层目录列表（不递归）。folders 在前、files 在后，按 name 排序。"""
    full = _safe_path(path)
    if not full.is_dir():
        raise HTTPException(400, "path is not a directory")
    rel_base = path.strip("/")
    out: list[dict] = []
    items = sorted(full.iterdir(), key=lambda p: (p.is_file(), p.name))
    for p in items:
        if p.name.startswith("."):
            continue  # 跳隐藏文件
        rel = f"{rel_base}/{p.name}" if rel_base else p.name
        node = {
            "id": f"kb:{rel}",
            "name": p.name,
            "kind": "folder" if p.is_dir() else "file",
            "parentId": f"kb:{rel_base}" if rel_base else "kb-root",
            "source": "kb",
            "hidden": False,
            "kbPath": rel,
            "createdAt": "",
            "updatedAt": "",
        }
        if p.is_file():
            try:
                node["size"] = p.stat().st_size
            except OSError:
                node["size"] = 0
            node["mime"] = _infer_mime(p.name)
        out.append(node)
    return out


@router.get("/file")
def get_kb_file(path: str = Query(...)):
    """读单个文件。文本类返 text/json，二进制返 binary stream。"""
    full = _safe_path(path)
    if not full.is_file():
        raise HTTPException(400, "path is not a file")
    if full.stat().st_size > MAX_FILE_BYTES:
        raise HTTPException(413, f"file too large (>{MAX_FILE_BYTES} bytes)")
    mime = _infer_mime(full.name)
    if mime in ("text/markdown", "text/plain", "application/json", "text/html"):
        try:
            return PlainTextResponse(
                full.read_text(encoding="utf-8"),
                media_type=mime,
            )
        except UnicodeDecodeError:
            pass
    # v0.27: 让 pdf / 图片 inline 预览，不强制下载（FastAPI FileResponse 默认 attachment）
    from urllib.parse import quote
    headers = {
        "Content-Disposition": f"inline; filename*=utf-8''{quote(full.name)}"
    }
    return FileResponse(full, media_type=mime, headers=headers)


@router.get("/stats", response_model=dict)
def kb_stats():
    """供前端展示用：kb 总文件数 / 子目录数 / 总字节"""
    if not KB_ROOT.exists():
        return {"exists": False, "subdirs": 0, "files": 0, "bytes": 0}
    subdirs = sum(1 for p in KB_ROOT.iterdir() if p.is_dir() and not p.name.startswith("."))
    files = 0
    total = 0
    for p in KB_ROOT.rglob("*"):
        if p.is_file() and not p.name.startswith("."):
            files += 1
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return {"exists": True, "subdirs": subdirs, "files": files, "bytes": total}
