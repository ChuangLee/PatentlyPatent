"""run 结束时把 AgentEvent dump 成 jsonl，落到 .ai-internal/_runs/<run_id>.jsonl。

同时提供 feed_plan_snapshot(snap, ev, seq) helper，把单条 SSE 事件喂给 PlanSnapshotState。

可见性：
  - hidden=True + readonly=True
  - 员工默认看不到 .ai-internal/
  - admin 文件树视图忽略 hidden 字段可见
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from .models import AgentEvent, FileNode
from .plan_snapshot import PlanSnapshotState

logger = logging.getLogger(__name__)


# ─── plan_snapshot 喂食 ───────────────────────────────────────────────────

_FILE_ID_RE = re.compile(r"file_id=([A-Za-z0-9_-]+)")


def feed_plan_snapshot(snap: PlanSnapshotState, ev: dict, seq: int) -> None:
    """单条 SSE 事件 → 喂给 plan_snapshot。容错：失败仅 log，不抛。"""
    if not snap:
        return
    try:
        etype = ev.get("type", "")
        if etype == "tool_use":
            name = ev.get("name", "") or ""
            # MCP 工具名前缀 'mcp__patent-tools__'；兼容裸名
            short = name.split("__")[-1] if "__" in name else name
            if short == "update_plan":
                inp = ev.get("input") or {}
                steps_json = inp.get("steps_json") if isinstance(inp, dict) else None
                snap.apply_update(steps_json, history_event_seq=seq)
        elif etype == "tool_result":
            # 在 result text 里 grep file_id=...
            text = ev.get("text", "") or ""
            for fid in _FILE_ID_RE.findall(text):
                snap.record_artifact(fid)
        snap.bump_seq(seq)
    except Exception as exc:  # noqa: BLE001
        logger.warning("feed_plan_snapshot failed: %s", exc)


# ─── jsonl 落盘 ───────────────────────────────────────────────────────────


def _ensure_internal_runs_folder(db: Session, project_id: str) -> Optional[str]:
    """确保 `.ai-internal/_runs/` 文件夹存在，返回其 FileNode.id。失败返 None。"""
    try:
        internal_id = f"root-internal-{project_id}"
        internal = db.get(FileNode, internal_id)
        if internal is None:
            internal = (
                db.query(FileNode)
                .filter(
                    FileNode.project_id == project_id,
                    FileNode.parent_id.is_(None),
                    FileNode.source == "system",
                    FileNode.hidden.is_(True),
                )
                .first()
            )
        if internal is None:
            internal = FileNode(
                id=internal_id,
                project_id=project_id,
                name=".ai-internal",
                kind="folder",
                parent_id=None,
                source="system",
                hidden=True,
            )
            db.add(internal)
            db.flush()
        runs = (
            db.query(FileNode)
            .filter(
                FileNode.project_id == project_id,
                FileNode.parent_id == internal.id,
                FileNode.kind == "folder",
                FileNode.name == "_runs",
            )
            .first()
        )
        if runs is None:
            runs = FileNode(
                id=f"d-{uuid.uuid4().hex[:10]}",
                project_id=project_id,
                name="_runs",
                kind="folder",
                parent_id=internal.id,
                source="system",
                hidden=True,
                readonly=True,
            )
            db.add(runs)
            db.flush()
        return runs.id
    except Exception as exc:  # noqa: BLE001
        logger.warning("_ensure_internal_runs_folder failed: %s", exc)
        return None


_MAX_JSONL_CHARS = 5 * 1024 * 1024   # 5 MB 单文件上限；超出截断 + 末行说明


def dump_run_to_filenode_sync(run_id: str, project_id: Optional[str]) -> Optional[str]:
    """run 结束时调用。同步：在 to_thread 里跑。返回 FileNode.id 或 None。

    幂等：同 run_id 重复 dump 会覆盖旧 FileNode 内容。
    """
    if not project_id:
        return None
    from .db import SessionLocal

    db = SessionLocal()
    try:
        events = (
            db.query(AgentEvent)
            .filter(AgentEvent.run_id == run_id)
            .order_by(AgentEvent.seq.asc())
            .all()
        )
        if not events:
            return None

        lines: list[str] = []
        total = 0
        truncated = False
        for ev in events:
            try:
                payload = dict(ev.payload or {})
                # 删除 delta 单字符级 — 太碎；保留长度 ≥10 的（保住 LLM 回答骨架）
                if payload.get("type") == "delta" and len(payload.get("text", "")) < 5:
                    continue
                payload["seq"] = ev.seq
                payload["ts"] = ev.created_at.isoformat() if ev.created_at else None
                line = json.dumps(payload, ensure_ascii=False, default=str)
            except Exception:
                continue
            if total + len(line) + 1 > _MAX_JSONL_CHARS:
                truncated = True
                break
            lines.append(line)
            total += len(line) + 1

        if truncated:
            lines.append(json.dumps({
                "type": "_truncated",
                "note": f"输出超过 {_MAX_JSONL_CHARS//1024} KB 已截断",
                "total_events": len(events),
            }, ensure_ascii=False))

        content = "\n".join(lines)
        runs_folder_id = _ensure_internal_runs_folder(db, project_id)
        if not runs_folder_id:
            return None

        fname = f"{run_id}.jsonl"
        existing = (
            db.query(FileNode)
            .filter(
                FileNode.project_id == project_id,
                FileNode.parent_id == runs_folder_id,
                FileNode.name == fname,
            )
            .first()
        )
        if existing is not None:
            existing.content = content
            existing.size = len(content.encode("utf-8"))
            existing.updated_at = datetime.now(timezone.utc)
            db.commit()
            return existing.id

        fid = f"f-{uuid.uuid4().hex[:10]}"
        node = FileNode(
            id=fid,
            project_id=project_id,
            name=fname,
            kind="file",
            parent_id=runs_folder_id,
            source="system",
            hidden=True,
            readonly=True,
            mime="application/x-ndjson",
            content=content,
            size=len(content.encode("utf-8")),
        )
        db.add(node)
        db.commit()
        return fid
    except Exception as exc:  # noqa: BLE001
        logger.warning("dump_run_to_filenode failed run=%s: %s", run_id, exc)
        try:
            db.rollback()
        except Exception:
            pass
        return None
    finally:
        db.close()
