"""断点续作：plan_snapshot 的 diff + artifact 归属 + DB UPSERT。

核心数据结构（Project.plan_snapshot_json）：
    {
        "run_id": "r-xxx",
        "endpoint": "interview" | "mine_full",
        "updated_at": ISO,
        "history_event_seq": int,  # resume 时取该 seq 及以前的 AgentEvent 作为对话历史
        "steps": [
            {
                "id": "s1",
                "title": "...",
                "status": "pending|in_progress|completed|failed",
                "started_at": ISO|None,
                "completed_at": ISO|None,
                "artifact_file_ids": ["f-..."],
                "artifact_summary": str | None,
            },
            ...
        ],
    }

调用约定（agent_sdk_spike _stream_query 内）：
    snap = PlanSnapshotState(project_id, run_id, endpoint)
    snap.load_from_db(db)
    ...
    snap.apply_update(steps_json, history_event_seq)         # 来自 update_plan tool_use
    snap.record_artifact(file_id)                            # 来自 file_write_section/save_research 返回
    snap.flush(db)                                            # UPSERT 回 Project.plan_snapshot_json
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import uuid

from sqlalchemy.orm import Session

from .models import FileNode, Project

logger = logging.getLogger(__name__)


_VALID_STATUS = {"pending", "in_progress", "completed", "failed"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_step(raw: dict) -> dict:
    """把 LLM 给的一条 step dict 校正为内部 schema。容忍缺字段。"""
    sid = str(raw.get("id") or "").strip() or f"s{id(raw) & 0xffff:x}"
    title = str(raw.get("title") or "").strip()[:512]
    status = str(raw.get("status") or "pending").strip().lower()
    if status not in _VALID_STATUS:
        status = "pending"
    artifact_files = raw.get("artifact_files")
    if not isinstance(artifact_files, list):
        artifact_files = []
    artifact_files = [str(x).strip() for x in artifact_files if str(x).strip()][:20]
    artifact_summary = raw.get("artifact_summary")
    if artifact_summary is not None:
        artifact_summary = str(artifact_summary).strip()[:2000] or None
    return {
        "id": sid,
        "title": title,
        "status": status,
        "started_at": None,
        "completed_at": None,
        "artifact_file_ids": [],
        "artifact_file_paths": artifact_files,   # LLM 显式声明的路径（与 ids 互补）
        "artifact_summary": artifact_summary,
    }


class PlanSnapshotState:
    """单 run 期间的 plan_snapshot 状态机。常驻内存，run 结束 flush。"""

    def __init__(self, project_id: str, run_id: str, endpoint: str):
        self.project_id = project_id
        self.run_id = run_id
        self.endpoint = endpoint
        self.steps: list[dict] = []
        self.history_event_seq: int = 0
        self.current_step_id: Optional[str] = None
        # 自动归属 buffer：当前 in_progress step 期间产生的 file_id
        self._artifact_buffer: list[str] = []
        self._dirty = False

    # ─── 加载已有快照（同 run 续作 / 重启 backend）───────────────────────

    def load_from_db(self, db: Session) -> None:
        proj = db.get(Project, self.project_id)
        if not proj or not proj.plan_snapshot_json:
            return
        snap = proj.plan_snapshot_json
        if not isinstance(snap, dict):
            return
        # 只在 run_id 匹配时加载已有 steps（跨 run 不复用，但保留已完成 step 由
        # /resume 端点单独拼装到 prompt，不在这里重放）
        if snap.get("run_id") == self.run_id:
            steps = snap.get("steps") or []
            if isinstance(steps, list):
                self.steps = [s for s in steps if isinstance(s, dict)]
            self.history_event_seq = int(snap.get("history_event_seq") or 0)

    # ─── 来自 update_plan 工具调用 ─────────────────────────────────────

    def apply_update(self, steps_raw: Any, history_event_seq: int) -> dict:
        """LLM 调 update_plan 时调用。返回 diff 信息（哪些 step 刚 transition）。"""
        if isinstance(steps_raw, str):
            try:
                steps_raw = json.loads(steps_raw or "[]")
            except Exception:
                steps_raw = []
        if not isinstance(steps_raw, list):
            steps_raw = []

        prev_by_id = {s["id"]: s for s in self.steps if isinstance(s, dict) and s.get("id")}
        new_steps: list[dict] = []
        transitions: list[dict] = []   # [{id, title, from, to}]

        for raw in steps_raw:
            if not isinstance(raw, dict):
                continue
            n = _normalize_step(raw)
            prev = prev_by_id.get(n["id"])
            if prev:
                # 保留旧 step 的 started_at / completed_at / artifact_file_ids
                n["started_at"] = prev.get("started_at")
                n["completed_at"] = prev.get("completed_at")
                # 已 completed 的 step 不允许被 LLM 倒退；保护已积累的 artifact_file_ids
                prev_status = prev.get("status", "pending")
                if prev_status == "completed" and n["status"] != "completed":
                    n["status"] = "completed"
                n["artifact_file_ids"] = list(prev.get("artifact_file_ids") or [])
                # artifact_summary：LLM 新显式声明覆盖旧的，否则保留
                if n["artifact_summary"] is None:
                    n["artifact_summary"] = prev.get("artifact_summary")
            # status transition
            now = _now_iso()
            if n["status"] == "in_progress" and not n["started_at"]:
                n["started_at"] = now
            if n["status"] in ("completed", "failed") and not n["completed_at"]:
                n["completed_at"] = now
                # flush 当前 buffer 到这个 step
                if self.current_step_id == n["id"] and self._artifact_buffer:
                    n["artifact_file_ids"] = list({*n["artifact_file_ids"], *self._artifact_buffer})
                    self._artifact_buffer.clear()
            prev_status = (prev or {}).get("status", "pending")
            if prev_status != n["status"]:
                transitions.append({
                    "id": n["id"],
                    "title": n["title"],
                    "from": prev_status,
                    "to": n["status"],
                })
            new_steps.append(n)

        # 维护 current_step_id：取最后一个 in_progress
        new_current = next(
            (s["id"] for s in reversed(new_steps) if s["status"] == "in_progress"),
            None,
        )
        if new_current != self.current_step_id:
            # 切换 step 时把残留 buffer flush 到旧 step（如果它已 completed/failed 没拿走）
            if self.current_step_id and self._artifact_buffer:
                for s in new_steps:
                    if s["id"] == self.current_step_id:
                        s["artifact_file_ids"] = list({*s["artifact_file_ids"], *self._artifact_buffer})
                        break
                self._artifact_buffer.clear()
            self.current_step_id = new_current

        self.steps = new_steps
        self.history_event_seq = max(self.history_event_seq, int(history_event_seq or 0))
        self._dirty = True
        return {"transitions": transitions, "current_step_id": self.current_step_id}

    # ─── 来自 file_write_section / save_research / bq_*等 ───────────────

    def record_artifact(self, file_id: Optional[str]) -> None:
        if not file_id:
            return
        if not self.current_step_id:
            # 还没声明 plan：忽略
            return
        if file_id in self._artifact_buffer:
            return
        self._artifact_buffer.append(file_id)
        self._dirty = True

    # ─── seq 推进（每条 AgentEvent 之后调）─────────────────────────────

    def bump_seq(self, seq: int) -> None:
        if seq > self.history_event_seq:
            self.history_event_seq = seq
            self._dirty = True

    # ─── 落盘 ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "endpoint": self.endpoint,
            "updated_at": _now_iso(),
            "history_event_seq": self.history_event_seq,
            "steps": self.steps,
        }

    def flush(self, db: Session) -> None:
        """UPSERT 到 Project.plan_snapshot_json + 同步镜像到 「AI 输出/项目计划.md」。容错：失败不抛。"""
        if not self._dirty:
            return
        try:
            proj = db.get(Project, self.project_id)
            if not proj:
                return
            snap_dict = self.to_dict()
            proj.plan_snapshot_json = snap_dict
            # 同步镜像到人可读 markdown（员工/admin 在文件树就能看进度）
            try:
                mirror_plan_to_markdown(db, self.project_id, snap_dict, project_title=proj.title)
            except Exception as exc:  # noqa: BLE001
                logger.warning("plan markdown mirror failed: %s", exc)
            db.commit()
            self._dirty = False
        except Exception as exc:  # noqa: BLE001
            logger.warning("plan_snapshot flush failed: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass

    # ─── run 终态：把残留 buffer 落到 current step ──────────────────────

    def finalize(self, db: Session, run_status: str = "completed") -> None:
        """run 结束时调。把未 flush 的 buffer 落给 current step。"""
        if self.current_step_id and self._artifact_buffer:
            for s in self.steps:
                if s["id"] == self.current_step_id:
                    s["artifact_file_ids"] = list({*s["artifact_file_ids"], *self._artifact_buffer})
                    break
            self._artifact_buffer.clear()
            self._dirty = True
        self.flush(db)


# ─── 镜像到「AI 输出/项目计划.md」 ──────────────────────────────────────


_PLAN_MD_NAME = "项目计划.md"
_AI_FOLDER_NAME = "AI 输出"
_STATUS_ICON = {
    "completed": "✅",
    "in_progress": "🔄",
    "pending": "⬜",
    "failed": "❌",
}


def _ensure_ai_output_folder(db: Session, project_id: str) -> str | None:
    """返回 AI 输出 文件夹 FileNode.id；不存在则创建（source='ai', 非 hidden）。"""
    folder = (
        db.query(FileNode)
        .filter(
            FileNode.project_id == project_id,
            FileNode.kind == "folder",
            FileNode.name == _AI_FOLDER_NAME,
            FileNode.parent_id.is_(None),
        )
        .first()
    )
    if folder:
        return folder.id
    try:
        fid = f"d-{uuid.uuid4().hex[:10]}"
        folder = FileNode(
            id=fid,
            project_id=project_id,
            name=_AI_FOLDER_NAME,
            kind="folder",
            parent_id=None,
            source="ai",
            hidden=False,
        )
        db.add(folder)
        db.flush()
        return fid
    except Exception as exc:  # noqa: BLE001
        logger.warning("create AI 输出 folder failed: %s", exc)
        return None


def _resolve_file_path(db: Session, project_id: str, fid: str) -> str | None:
    node = (
        db.query(FileNode)
        .filter(FileNode.project_id == project_id, FileNode.id == fid)
        .first()
    )
    if not node:
        return None
    parts = [node.name]
    cur = node
    for _ in range(5):
        if not cur.parent_id:
            break
        parent = db.get(FileNode, cur.parent_id)
        if not parent:
            break
        parts.insert(0, parent.name)
        cur = parent
    return "/".join(parts)


def _render_plan_markdown(snap: dict, project_title: str, file_paths_by_id: dict[str, str]) -> str:
    steps = snap.get("steps") or []
    total = len(steps)
    done = sum(1 for s in steps if s.get("status") == "completed")
    failed = sum(1 for s in steps if s.get("status") == "failed")
    cur = next((s for s in steps if s.get("status") == "in_progress"), None)
    lines: list[str] = []
    lines.append(f"# 项目计划 — {project_title}")
    lines.append("")
    lines.append(
        f"> 进度 **{done} / {total}** · 失败 {failed} · 更新时间 {snap.get('updated_at','')}"
    )
    if cur:
        lines.append(f"> 当前进行中：**{cur.get('title','')}**（{cur.get('id','')}）")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 步骤")
    lines.append("")
    for s in steps:
        icon = _STATUS_ICON.get(s.get("status", "pending"), "⬜")
        sid = s.get("id", "?")
        title = s.get("title", "")
        lines.append(f"### {icon} [{sid}] {title}")
        ts_parts = []
        if s.get("started_at"):
            ts_parts.append(f"开始 {s['started_at']}")
        if s.get("completed_at"):
            ts_parts.append(f"完成 {s['completed_at']}")
        if ts_parts:
            lines.append(f"<small>{' · '.join(ts_parts)}</small>")
        if s.get("artifact_summary"):
            lines.append("")
            lines.append(f"**小结**：{s['artifact_summary']}")
        # 产出文件链接
        artifacts: list[str] = []
        for fid in (s.get("artifact_file_ids") or []):
            path = file_paths_by_id.get(fid)
            if path:
                artifacts.append(path)
        artifacts.extend(s.get("artifact_file_paths") or [])
        artifacts = list(dict.fromkeys(artifacts))   # 去重保序
        if artifacts:
            lines.append("")
            lines.append("**产出**：")
            for p in artifacts:
                lines.append(f"- `{p}`")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("> 本文件由 AI 自动维护，每次更新计划同步覆盖。")
    return "\n".join(lines)


def mirror_plan_to_markdown(
    db: Session, project_id: str, snap: dict, *, project_title: str = "",
) -> str | None:
    """把当前 plan_snapshot 渲染成 markdown，写到「AI 输出/项目计划.md」（覆盖式）。

    幂等：同 project 重复调用只 update 一个 FileNode；不创建多份。
    """
    parent_id = _ensure_ai_output_folder(db, project_id)
    if not parent_id:
        return None
    # 解析 artifact_file_ids → 路径，给 markdown 渲染用
    all_ids: set[str] = set()
    for s in (snap.get("steps") or []):
        for fid in (s.get("artifact_file_ids") or []):
            all_ids.add(fid)
    paths: dict[str, str] = {}
    if all_ids:
        for fid in all_ids:
            p = _resolve_file_path(db, project_id, fid)
            if p:
                paths[fid] = p
    content = _render_plan_markdown(snap, project_title or project_id, paths)
    size = len(content.encode("utf-8"))

    existing = (
        db.query(FileNode)
        .filter(
            FileNode.project_id == project_id,
            FileNode.parent_id == parent_id,
            FileNode.name == _PLAN_MD_NAME,
        )
        .first()
    )
    if existing:
        existing.content = content
        existing.size = size
        existing.mime = "text/markdown"
        db.flush()
        return existing.id
    fid = f"f-{uuid.uuid4().hex[:10]}"
    node = FileNode(
        id=fid,
        project_id=project_id,
        name=_PLAN_MD_NAME,
        kind="file",
        parent_id=parent_id,
        source="ai",
        hidden=False,
        readonly=False,
        mime="text/markdown",
        content=content,
        size=size,
    )
    db.add(node)
    db.flush()
    return fid


# ─── /resume 端点用：把已完成 / 未完成 steps 总结成 prompt 头 ──────────


def summarize_for_resume(snap: dict, file_paths_by_id: dict[str, str] | None = None) -> str:
    """生成续作 prompt 头。snap 是 Project.plan_snapshot_json。"""
    file_paths_by_id = file_paths_by_id or {}
    steps = snap.get("steps") or []
    completed = [s for s in steps if s.get("status") == "completed"]
    pending = [s for s in steps if s.get("status") not in ("completed", "failed")]
    failed = [s for s in steps if s.get("status") == "failed"]

    def _fmt_artifacts(s: dict) -> str:
        ids = s.get("artifact_file_ids") or []
        paths = s.get("artifact_file_paths") or []
        names = []
        for fid in ids:
            p = file_paths_by_id.get(fid)
            if p:
                names.append(p)
        names.extend(paths)
        if not names:
            return ""
        return "  产出：" + " / ".join(dict.fromkeys(names)[:5])

    lines: list[str] = []
    lines.append("## 上次会话的工作进度（续作）")
    if completed:
        lines.append(f"\n### 已完成 {len(completed)} 步（**不要重做**）")
        for s in completed:
            lines.append(f"- [{s['id']}] {s.get('title','')}")
            arts = _fmt_artifacts(s)
            if arts:
                lines.append(arts)
            if s.get("artifact_summary"):
                lines.append(f"  小结：{s['artifact_summary']}")
    if failed:
        lines.append(f"\n### 失败 {len(failed)} 步（可重试，但请说明原因）")
        for s in failed:
            lines.append(f"- [{s['id']}] {s.get('title','')}")
    lines.append(f"\n### 待办 {len(pending)} 步（**从这里续作**）")
    for s in pending:
        marker = "← 续作起点" if s is pending[0] else ""
        lines.append(f"- [{s['id']}] {s.get('title','')} {marker}".rstrip())
    lines.append(
        "\n**指令**：调 `update_plan` 时保留**所有已完成 step 的 id/title/status=completed** 不变，"
        "仅推进待办部分。续作完毕后总结你这次新增的工作（不要重述已完成的）。"
    )
    return "\n".join(lines)
