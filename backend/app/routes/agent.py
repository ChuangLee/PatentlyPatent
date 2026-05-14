"""v0.16 spike-B: Agent SDK 单端点 SSE 路由。

POST /api/agent/mine_spike { idea, max_turns? }  -> SSE stream
事件类型：thinking / tool_use / tool_result / delta / done / error

v0.18-D: 增加 A/B 对比端点
POST /api/agent/ab_compare/{project_id} { idea } -> JSON
  并行（顺序）跑 mining 老路径 + agent 路径，落盘到 .ai-internal/_compare/，
  返回 {mining_file_id, agent_file_id, mining_md, agent_md, summary}
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import json
import logging
import time
import uuid
from datetime import timezone as _tz

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from ..agent_sdk_spike import agent_mine_stream
from .. import agent_section_demo
from ..agent_interview import interview_stream
from ..agent_section_demo import mine_section_via_agent
from ..budget import BudgetBlocked, ensure_not_blocked, update_after_run
from ..concurrency import SSEBusy, acquire_sse_slot, release_sse_slot
from ..config import settings
from ..db import SessionLocal, get_db
from ..mining import build_prior_art_section_legacy, _DOMAIN_LABEL
from ..models import AgentEvent, AgentRun, AgentRunLog, FileNode, Project
from ..plan_snapshot import PlanSnapshotState
from ..run_archive import dump_and_purge_events_sync, feed_plan_snapshot, read_run_events_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# ─── v0.36: interview agent —— 资深专利代理人对话式追问 ─────────────────────


class InterviewMessage(BaseModel):
    role: str  # 'user' | 'agent'
    content: str


class InterviewRequest(BaseModel):
    user_msg: str | None = None
    history: list[InterviewMessage] | None = None


def _gather_interview_inputs(pid: str) -> dict:
    """从 DB 读项目 + 已生成的 5 节 markdown + 上传文件清单。

    sections 优先取 .ai-internal/_compare/full/<sect>.md（mineFull 落地），
    缺则 fallback 到 AI 输出/01-xx.md（老 mining 路径）。
    """
    db = SessionLocal()
    try:
        p = db.get(Project, pid)
        if not p:
            return {}
        all_files = (
            db.query(FileNode)
            .filter(FileNode.project_id == pid)
            .all()
        )
        by_id = {f.id: f for f in all_files}
        by_parent: dict[str | None, list[FileNode]] = {}
        for f in all_files:
            by_parent.setdefault(f.parent_id, []).append(f)

        def _find_folder(parent_id: str | None, name: str) -> FileNode | None:
            for f in by_parent.get(parent_id, []):
                if f.kind == "folder" and f.name == name:
                    return f
            return None

        # sections from mineFull hidden folder
        sections: dict[str, str] = {}
        internal = next(
            (f for f in by_parent.get(None, []) if f.kind == "folder" and f.name == ".ai-internal"),
            None,
        )
        if internal:
            compare = _find_folder(internal.id, "_compare")
            if compare:
                full = _find_folder(compare.id, "full")
                if full:
                    for f in by_parent.get(full.id, []):
                        if f.kind == "file" and f.content:
                            sections[f.name] = f.content

        # fallback: AI 输出/01-xx.md (legacy mining)
        ai_root = next(
            (f for f in by_parent.get(None, []) if f.kind == "folder" and f.name == "AI 输出"),
            None,
        )
        if ai_root and not sections:
            for f in by_parent.get(ai_root.id, []):
                if f.kind == "file" and f.name.endswith(".md") and not f.name.startswith("_"):
                    sections[f.name] = f.content or ""

        # uploads under 我的资料/
        uploads_root = next(
            (f for f in by_parent.get(None, []) if f.kind == "folder" and f.name == "我的资料"),
            None,
        )
        uploads: list[dict] = []
        if uploads_root:
            for f in by_parent.get(uploads_root.id, []):
                if f.kind == "file":
                    uploads.append({
                        "name": f.name,
                        "mime": f.mime or "?",
                        "size": f.size or 0,
                    })

        domain = p.custom_domain or _DOMAIN_LABEL.get(p.domain or "", p.domain or "其他")
        return {
            "idea": p.description or "",
            "title": p.title or "",
            "domain": domain,
            "sections": sections,
            "uploads": uploads,
        }
    finally:
        db.close()


@router.post("/interview/{project_id}")
async def interview(project_id: str, body: InterviewRequest):
    """资深专利代理人对话式追问端点。

    - 首轮（history 空）：基于初稿挑 ≤3 个最关键的事实/方向问题
    - 后续轮（带 user_msg + history）：消化用户答 → 续问 ≤3 个 / 或宣告 [READY_FOR_DOCX]

    每次调用都会创建 AgentRun + 每个 event 落 AgentEvent + 维护 plan_snapshot
    + 结束时 dump 到 .ai-internal/_runs/{run_id}.jsonl
    """
    try:
        ensure_not_blocked()
    except BudgetBlocked as exc:
        raise HTTPException(503, f"今日预算已超限：${exc.daily_sum:.4f}")
    try:
        await acquire_sse_slot("interview")
    except SSEBusy:
        raise HTTPException(503, "服务繁忙，请稍候")

    inputs = await asyncio.to_thread(_gather_interview_inputs, project_id)
    if not inputs:
        release_sse_slot("interview")
        raise HTTPException(404, f"project {project_id} not found")

    # 把当轮 user_msg 拼到 history 末尾
    history = [m.model_dump() for m in (body.history or [])]
    if body.user_msg:
        history.append({"role": "user", "content": body.user_msg})

    return await _interview_sse_response(
        project_id=project_id,
        idea=inputs["idea"],
        title=inputs["title"],
        domain=inputs["domain"],
        sections=inputs["sections"],
        uploads=inputs["uploads"],
        history=history,
    )


@router.post("/interview/{project_id}/resume")
async def interview_resume(project_id: str):
    """断点续作：从 Project.plan_snapshot_json 拼装 history 摘要 + 已完成/待办列表，
    复用 interview_stream 但 prompt 头明确告诉 LLM「不要重做已完成步骤」。
    """
    try:
        ensure_not_blocked()
    except BudgetBlocked as exc:
        raise HTTPException(503, f"今日预算已超限：${exc.daily_sum:.4f}")

    # 同步取 plan_snapshot + 历史 events
    def _gather() -> dict | None:
        from ..plan_snapshot import summarize_for_resume
        db = SessionLocal()
        try:
            proj = db.get(Project, project_id)
            if not proj:
                return None
            snap = proj.plan_snapshot_json
            if not isinstance(snap, dict) or not snap.get("steps"):
                return {"error": "no_snapshot"}
            steps = snap.get("steps") or []
            pending = [s for s in steps if isinstance(s, dict) and s.get("status") not in ("completed", "failed")]
            if not pending:
                return {"error": "all_completed"}
            # 找 artifact_file_id → 路径 映射
            ids: set[str] = set()
            for s in steps:
                for fid in (s.get("artifact_file_ids") or []):
                    ids.add(fid)
            paths: dict[str, str] = {}
            if ids:
                rows = (
                    db.query(FileNode)
                    .filter(FileNode.project_id == project_id, FileNode.id.in_(ids))
                    .all()
                )
                for r in rows:
                    paths[r.id] = _resolve_path(db, project_id, r)
            history_seq = int(snap.get("history_event_seq") or 0)
            # 历史事件统一从 read_run_events_sync 读：优先 .ai-internal/_runs/{run_id}.jsonl，
            # fallback AgentEvent 表（run 还没 dump 的运行中场景）。
            all_rows = read_run_events_sync(project_id, snap.get("run_id") or "")
            history_events = [r for r in all_rows if int(r.get("seq", 0)) <= history_seq]
            condensed_history = _condense_events(history_events)
            resume_head = summarize_for_resume(snap, file_paths_by_id=paths)
            return {
                "resume_head": resume_head,
                "condensed_history": condensed_history,
                "title": proj.title,
                "domain": proj.custom_domain or _DOMAIN_LABEL.get(proj.domain or "", proj.domain or "其他"),
            }
        finally:
            db.close()

    data = await asyncio.to_thread(_gather)
    if data is None:
        raise HTTPException(404, f"project {project_id} not found")
    if "error" in data:
        if data["error"] == "no_snapshot":
            raise HTTPException(409, "暂无续作进度，请使用「开始挖掘」")
        if data["error"] == "all_completed":
            raise HTTPException(409, "上次工作计划已全部完成，请使用「重新挖掘」")

    try:
        await acquire_sse_slot("interview")
    except SSEBusy:
        raise HTTPException(503, "服务繁忙，请稍候")

    inputs = await asyncio.to_thread(_gather_interview_inputs, project_id)
    if not inputs:
        release_sse_slot("interview")
        raise HTTPException(404, f"project {project_id} not found")

    # 把续作头 + 历史摘要拼成 user_msg
    resume_msg = (
        f"{data['resume_head']}\n\n"
        f"## 上次对话摘要\n{data['condensed_history']}\n\n"
        "请从待办区第一个未完成步骤续作。"
    )
    history = [{"role": "user", "content": resume_msg}]

    return await _interview_sse_response(
        project_id=project_id,
        idea=inputs["idea"],
        title=inputs["title"],
        domain=inputs["domain"],
        sections=inputs["sections"],
        uploads=inputs["uploads"],
        history=history,
    )


def _resolve_path(db: Session, project_id: str, node: FileNode) -> str:
    """从 FileNode 反向推断「父文件夹/.../文件名」路径（≤3 层）。失败返 name。"""
    try:
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
    except Exception:
        return node.name


def _condense_events(events: list[dict], max_chars: int = 8000) -> str:
    """把 AgentEvent 流压缩成续作 prompt 友好的对话摘要。

    保留：user 发问 / agent 文本回答（≥30 字段）/ tool_use 名+小结。
    丢弃：delta（碎片）/ tool_result 全文 / thinking。
    """
    lines: list[str] = []
    text_buf: list[str] = []  # delta 拼接
    for e in events:
        payload = e.get("payload") or {}
        etype = payload.get("type")
        if etype == "delta":
            txt = payload.get("text", "")
            if txt:
                text_buf.append(txt)
            continue
        # 在非 delta 事件处 flush text_buf 作为 agent 回答
        if text_buf:
            agent_text = "".join(text_buf).strip()
            if len(agent_text) >= 30:
                lines.append(f"[Agent] {agent_text[:600]}")
            text_buf.clear()
        if etype == "tool_use":
            name = payload.get("name") or ""
            short = name.split("__")[-1] if "__" in name else name
            inp = payload.get("input") or {}
            keys = []
            if isinstance(inp, dict):
                for k in ("query", "keywords", "keyword", "name", "publication_number"):
                    if k in inp and inp[k]:
                        keys.append(f"{k}={str(inp[k])[:80]}")
                        break
            lines.append(f"[Tool] {short}({', '.join(keys)})")
        elif etype == "section_done":
            lines.append(f"[Section done] {payload.get('name','?')}")
        elif etype == "error":
            lines.append(f"[Error] {payload.get('message','?')}")
    # flush 残留 delta
    if text_buf:
        agent_text = "".join(text_buf).strip()
        if len(agent_text) >= 30:
            lines.append(f"[Agent] {agent_text[:600]}")
    out = "\n".join(lines)
    if len(out) > max_chars:
        # 尾部截断（保留早期 + 后期信息）
        keep_head = max_chars // 3
        keep_tail = max_chars - keep_head - 64
        out = out[:keep_head] + "\n…（中间已省略）…\n" + out[-keep_tail:]
    return out or "（上次对话内容已超出保留窗口）"


async def _interview_sse_response(
    *,
    project_id: str,
    idea: str,
    title: str,
    domain: str,
    sections,
    uploads,
    history: list[dict],
):
    """interview / interview-resume 共用 SSE 响应：创建 AgentRun + 全程喂 plan_snapshot + 落 jsonl。"""
    run_id = _new_run_id()
    # 创建 AgentRun 行
    def _create_run():
        db = SessionLocal()
        try:
            db.add(AgentRun(
                id=run_id,
                project_id=project_id,
                endpoint="interview",
                status="running",
                idea=(history[-1].get("content") if history else None) or idea[:512],
            ))
            db.commit()
        finally:
            db.close()
    await asyncio.to_thread(_create_run)

    snap = PlanSnapshotState(project_id, run_id, "interview")
    seq = 0
    last_error: str | None = None
    total_cost = 0.0
    total_turns = 0

    async def gen():
        nonlocal seq, last_error, total_cost, total_turns
        # 首帧告诉前端 run_id（前端可缓存做断线重连）
        yield {
            "event": "run_started",
            "data": json.dumps({"type": "run_started", "run_id": run_id}, ensure_ascii=False),
        }
        try:
            async for ev in interview_stream(
                idea=idea,
                title=title,
                domain=domain,
                sections=sections,
                uploads=uploads,
                history=history,
                project_id=project_id,
            ):
                seq += 1
                # 落 AgentEvent + 喂 plan_snapshot（容错，失败不阻塞流）
                await asyncio.to_thread(_persist_event_sync, run_id, project_id, seq, ev)
                await asyncio.to_thread(feed_plan_snapshot, snap, ev, seq)
                # plan_snapshot 累计后 flush
                if ev.get("type") in ("tool_use", "tool_result", "done"):
                    db = SessionLocal()
                    try:
                        await asyncio.to_thread(snap.flush, db)
                    finally:
                        db.close()
                etype = ev.get("type")
                if etype == "done":
                    if ev.get("total_cost_usd"):
                        total_cost += float(ev["total_cost_usd"])
                    if ev.get("num_turns"):
                        total_turns += int(ev["num_turns"])
                elif etype == "error":
                    last_error = ev.get("message")
                yield {
                    "event": etype or "message",
                    "data": json.dumps({**ev, "run_id": run_id}, ensure_ascii=False),
                }
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            logger.exception("interview run %s failed", run_id)
            try:
                yield {
                    "event": "error",
                    "data": json.dumps({"type": "error", "message": last_error}, ensure_ascii=False),
                }
            except Exception:
                pass
        finally:
            release_sse_slot("interview")
            # finalize snap + close AgentRun + dump jsonl
            def _finalize():
                db = SessionLocal()
                try:
                    snap.finalize(db, "error" if last_error else "completed")
                finally:
                    db.close()
                _update_run_sync(
                    run_id,
                    status="error" if last_error else "completed",
                    finished_at=_dt.datetime.now(_tz.utc),
                    total_cost_usd=total_cost or None,
                    num_turns=total_turns or None,
                    error=last_error,
                )
                dump_and_purge_events_sync(run_id, project_id)
            try:
                await asyncio.to_thread(_finalize)
            except Exception:  # noqa: BLE001
                logger.warning("interview finalize failed run=%s", run_id, exc_info=True)
            try:
                await asyncio.to_thread(update_after_run, "interview")
            except Exception:  # noqa: BLE001
                pass

    return EventSourceResponse(gen())


class MineSpikeRequest(BaseModel):
    idea: str
    max_turns: int = 8


@router.post("/mine_spike")
async def mine_spike(body: MineSpikeRequest):
    # v0.21: 预算硬阻断 + SSE 并发限流
    try:
        ensure_not_blocked()
    except BudgetBlocked as exc:
        raise HTTPException(503, f"今日预算已超限：${exc.daily_sum:.4f}")
    try:
        await acquire_sse_slot("mine_spike")
    except SSEBusy:
        raise HTTPException(503, "服务繁忙，请稍候")

    async def gen():
        try:
            async for ev in agent_mine_stream(body.idea, max_turns=body.max_turns):
                yield {
                    "event": ev.get("type", "message"),
                    "data": json.dumps(ev, ensure_ascii=False),
                }
        finally:
            release_sse_slot("mine_spike")

    return EventSourceResponse(gen())


# ─── v0.18-D: A/B 对比落盘 ─────────────────────────────────────────────────

class ABCompareRequest(BaseModel):
    idea: str


def _get_or_create_compare_folder(db: Session, pid: str) -> str:
    """找到/创建 .ai-internal/_compare/ 文件夹，返回 folder id。"""
    internal_id = f"root-internal-{pid}"
    internal = db.get(FileNode, internal_id)
    if internal is None:
        # 兜底：按 name+hidden 找
        internal = (
            db.query(FileNode)
            .filter(
                FileNode.project_id == pid,
                FileNode.parent_id.is_(None),
                FileNode.source == "system",
                FileNode.hidden.is_(True),
            )
            .first()
        )
    if internal is None:
        # 项目老到没有 .ai-internal 根：现场补
        internal = FileNode(
            id=internal_id,
            project_id=pid,
            name=".ai-internal",
            kind="folder",
            parent_id=None,
            source="system",
            hidden=True,
        )
        db.add(internal)
        db.flush()

    compare = (
        db.query(FileNode)
        .filter(
            FileNode.project_id == pid,
            FileNode.parent_id == internal.id,
            FileNode.kind == "folder",
            FileNode.name == "_compare",
        )
        .first()
    )
    if compare is None:
        compare = FileNode(
            id=f"d-{uuid.uuid4().hex[:10]}",
            project_id=pid,
            name="_compare",
            kind="folder",
            parent_id=internal.id,
            source="system",
            hidden=True,
        )
        db.add(compare)
        db.flush()
    return compare.id


def _write_md_node(
    db: Session, pid: str, parent_id: str, name: str, content: str,
) -> str:
    """写一个 markdown FileNode；同名先删（A/B 反复跑覆盖落盘）。"""
    existing = (
        db.query(FileNode)
        .filter(
            FileNode.project_id == pid,
            FileNode.parent_id == parent_id,
            FileNode.name == name,
        )
        .first()
    )
    if existing is not None:
        db.delete(existing)
        db.flush()
    fid = f"f-{uuid.uuid4().hex[:10]}"
    node = FileNode(
        id=fid,
        project_id=pid,
        name=name,
        kind="file",
        parent_id=parent_id,
        source="system",
        hidden=True,
        mime="text/markdown",
        content=content,
        size=len(content.encode("utf-8")) if content else 0,
    )
    db.add(node)
    db.flush()
    return fid


async def _run_agent_prior_art(
    idea: str, project: Project, timeout: float = 25.0,
) -> tuple[str, dict]:
    """跑 agent 路径，把所有事件拼成 markdown。

    返回 (markdown, meta) — meta 含 tool_calls/error/raw_events_count 等。
    任何失败抛异常给上层捕获。
    """
    title = project.title or "未命名项目"
    domain = project.custom_domain or _DOMAIN_LABEL.get(project.domain or "", project.domain or "")
    deltas: list[str] = []
    tool_lines: list[str] = []
    tool_calls = 0
    err: str | None = None

    done_meta: dict = {}

    async def _run() -> None:
        nonlocal tool_calls, err
        async for ev in mine_section_via_agent(
            "prior_art",
            {
                "idea_text": idea,
                "title": title,
                "domain": domain,
                "project_id": project.id,
            },
        ):
            etype = ev.get("type")
            if etype == "delta":
                deltas.append(ev.get("text", ""))
            elif etype == "tool_use":
                tool_calls += 1
                tool_lines.append(
                    f"- **tool_use** `{ev.get('name','?')}` "
                    f"input=`{json.dumps(ev.get('input', {}), ensure_ascii=False)}`"
                )
            elif etype == "tool_result":
                txt = (ev.get("text") or "").strip()
                if len(txt) > 400:
                    txt = txt[:400] + "…"
                tool_lines.append(f"  - tool_result: {txt}")
            elif etype == "thinking":
                tool_lines.append(f"- *thinking*: {ev.get('text','')}")
            elif etype == "error":
                err = ev.get("message", "?")
            elif etype == "done":
                # v0.20: 抓 done event meta 给 ab_compare 写日志用
                done_meta["num_turns"] = ev.get("num_turns")
                done_meta["total_cost_usd"] = ev.get("total_cost_usd")
                done_meta["stop_reason"] = ev.get("stop_reason")

    await asyncio.wait_for(_run(), timeout=timeout)

    body = "".join(deltas).strip() or "(agent 未输出 delta)"
    header = (
        "# [agent 路径] 一、背景技术\n\n"
        f"> 由 agent_section_demo.mine_section_via_agent('prior_art') 生成\n"
        f"> tool 调用次数：{tool_calls}\n\n"
    )
    trace = (
        "\n\n---\n\n## Agent 调用链 trace\n\n" + "\n".join(tool_lines)
        if tool_lines
        else ""
    )
    md = header + body + trace
    return md, {
        "tool_calls": tool_calls,
        "error": err,
        "deltas_chars": len(body),
        "num_turns": done_meta.get("num_turns"),
        "total_cost_usd": done_meta.get("total_cost_usd"),
        "stop_reason": done_meta.get("stop_reason"),
    }


@router.post("/ab_compare/{project_id}")
async def ab_compare(
    project_id: str, body: ABCompareRequest, db: Session = Depends(get_db),
):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, f"project {project_id} not found")

    idea = (body.idea or p.description or "").strip()
    if not idea:
        raise HTTPException(400, "idea 为空且 project.description 也为空")

    title = p.title or "未命名项目"
    domain_label = p.custom_domain or _DOMAIN_LABEL.get(p.domain or "", p.domain or "其他")
    desc_safe = (p.description or "").strip() or "（用户报门时未填写描述，需在对话中补充）"

    # 1) mining 老路径（同步、纯模板）
    mining_section = build_prior_art_section_legacy(title, domain_label, desc_safe)
    mining_md = mining_section["content"]

    # 2) agent 路径（async，失败兜底返错）
    agent_md = ""
    agent_error: str | None = None
    agent_meta: dict = {}
    t_agent = time.monotonic()
    try:
        agent_md, agent_meta = await _run_agent_prior_art(idea, p)
        if agent_meta.get("error"):
            agent_error = agent_meta["error"]
    except asyncio.TimeoutError:
        agent_error = "agent timeout >25s"
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent path failed")
        agent_error = f"agent exception: {exc}"
    finally:
        # v0.19-D: ab_compare 的 agent 那条写一行日志（mining 那条是纯模板不写）
        try:
            _ab_log_db = SessionLocal()
            try:
                _stop_reason = agent_meta.get("stop_reason")
                _ab_log_db.add(AgentRunLog(
                    endpoint="ab_compare",
                    project_id=project_id,
                    idea=(idea or "")[:4000],
                    num_turns=agent_meta.get("num_turns"),
                    total_cost_usd=agent_meta.get("total_cost_usd"),
                    duration_ms=int((time.monotonic() - t_agent) * 1000),
                    stop_reason=(_stop_reason or None) and str(_stop_reason)[:32],
                    fallback_used=False,
                    error=(agent_error or None) and str(agent_error)[:2000],
                    is_mock=False,
                ))
                _ab_log_db.commit()
            except Exception:
                _ab_log_db.rollback()
                raise
            finally:
                _ab_log_db.close()
            # v0.21: 预算告警
            try:
                update_after_run("ab_compare")
            except Exception:  # noqa: BLE001
                pass
        except Exception as _exc:  # noqa: BLE001
            logger.warning("ab_compare agent_run_log write failed: %s", _exc)

    if not agent_md:
        agent_md = (
            "# [agent 路径] 一、背景技术\n\n"
            f"> ⚠️ agent 路径失败：{agent_error or 'unknown'}\n"
        )

    # 3) 落盘
    compare_folder_id = _get_or_create_compare_folder(db, project_id)
    mining_file_id = _write_md_node(
        db, project_id, compare_folder_id, "01-prior_art-mining.md", mining_md,
    )
    agent_file_id = _write_md_node(
        db, project_id, compare_folder_id, "01-prior_art-agent.md", agent_md,
    )
    db.commit()

    # 4) summary
    def _lines(s: str) -> int:
        return s.count("\n") + 1 if s else 0

    summary = {
        "mining_lines": _lines(mining_md),
        "agent_lines": _lines(agent_md),
        "mining_chars": len(mining_md),
        "agent_chars": len(agent_md),
        "char_diff": len(agent_md) - len(mining_md),
        "agent_tool_calls": agent_meta.get("tool_calls", 0),
        "agent_error": agent_error,
    }

    return {
        "mining_file_id": mining_file_id,
        "agent_file_id": agent_file_id,
        "mining_md": mining_md,
        "agent_md": agent_md,
        "summary": summary,
    }


# ─── v0.20: /mine_full/{project_id} —— 一次跑全 5 节，SSE 流式 ────────────────


_DEFAULT_FULL_SECTIONS = [
    "prior_art",
    "summary",
    "embodiments",
    "claims",
    "drawings_description",
]


class MineFullRequest(BaseModel):
    idea: str
    sections: list[str] | None = None


def _get_or_create_full_folder(db: Session, pid: str) -> str:
    """找/建 .ai-internal/_compare/full/ 文件夹，返回 folder id。"""
    compare_id = _get_or_create_compare_folder(db, pid)
    full = (
        db.query(FileNode)
        .filter(
            FileNode.project_id == pid,
            FileNode.parent_id == compare_id,
            FileNode.kind == "folder",
            FileNode.name == "full",
        )
        .first()
    )
    if full is None:
        full = FileNode(
            id=f"d-{uuid.uuid4().hex[:10]}",
            project_id=pid,
            name="full",
            kind="folder",
            parent_id=compare_id,
            source="ai",
            hidden=True,
        )
        db.add(full)
        db.flush()
        db.commit()
    return full.id


def _write_full_section(pid: str, sect: str, md: str) -> str:
    """短事务：写 .ai-internal/_compare/full/<sect>.md，返 file_id。"""
    db = SessionLocal()
    try:
        folder_id = _get_or_create_full_folder(db, pid)
        name = f"{sect}.md"
        existing = (
            db.query(FileNode)
            .filter(
                FileNode.project_id == pid,
                FileNode.parent_id == folder_id,
                FileNode.name == name,
            )
            .first()
        )
        if existing is not None:
            db.delete(existing)
            db.flush()
        fid = f"f-{uuid.uuid4().hex[:10]}"
        node = FileNode(
            id=fid,
            project_id=pid,
            name=name,
            kind="file",
            parent_id=folder_id,
            source="ai",
            hidden=True,
            mime="text/markdown",
            content=md,
            size=len(md.encode("utf-8")) if md else 0,
        )
        db.add(node)
        db.commit()
        return fid
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _write_run_log_sync(
    *,
    endpoint: str,
    project_id: str | None,
    idea: str | None,
    num_turns: int | None,
    total_cost_usd: float | None,
    duration_ms: int,
    stop_reason: str | None,
    fallback_used: bool,
    error: str | None,
    is_mock: bool,
) -> None:
    db = SessionLocal()
    try:
        row = AgentRunLog(
            endpoint=endpoint,
            project_id=project_id,
            idea=(idea or "")[:4000],
            num_turns=num_turns,
            total_cost_usd=total_cost_usd,
            duration_ms=duration_ms,
            stop_reason=(stop_reason or None) and str(stop_reason)[:32],
            fallback_used=bool(fallback_used),
            error=(error or None) and str(error)[:2000],
            is_mock=bool(is_mock),
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/mine_full/{project_id}")
async def mine_full(
    project_id: str, body: MineFullRequest, db: Session = Depends(get_db),
):
    sections = body.sections or list(_DEFAULT_FULL_SECTIONS)
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "project not found")

    idea_text = (body.idea or p.description or "").strip()
    if not idea_text:
        raise HTTPException(400, "idea 为空且 project.description 也为空")

    title = p.title or "未命名项目"
    domain_label = p.custom_domain or _DOMAIN_LABEL.get(p.domain or "", p.domain or "其他")

    # v0.21: 预算硬阻断 + SSE 并发限流
    try:
        ensure_not_blocked()
    except BudgetBlocked as exc:
        raise HTTPException(503, f"今日预算已超限：${exc.daily_sum:.4f}")
    try:
        await acquire_sse_slot("mine_full")
    except SSEBusy:
        raise HTTPException(503, "服务繁忙，请稍候")

    async def gen():
        t0 = time.monotonic()
        total_cost = 0.0
        total_turns = 0
        sections_done: list[str] = []
        last_error: str | None = None
        try:
            for sect in sections:
                yield {
                    "event": "section_start",
                    "data": json.dumps(
                        {"type": "section_start", "name": sect}, ensure_ascii=False,
                    ),
                }
                sect_md_parts: list[str] = []
                async for ev in agent_section_demo.mine_section_via_agent(
                    sect,
                    {
                        "idea_text": idea_text,
                        "title": title,
                        "domain": domain_label,
                        "project_id": project_id,
                    },
                ):
                    yield {
                        "event": ev.get("type", "message"),
                        "data": json.dumps(ev, ensure_ascii=False),
                    }
                    etype = ev.get("type")
                    if etype == "delta":
                        sect_md_parts.append(ev.get("text", ""))
                    elif etype == "done":
                        if ev.get("total_cost_usd"):
                            total_cost += float(ev["total_cost_usd"])
                        if ev.get("num_turns"):
                            total_turns += int(ev["num_turns"])
                    elif etype == "error":
                        last_error = ev.get("message")
                file_id = await asyncio.to_thread(
                    _write_full_section, project_id, sect, "".join(sect_md_parts),
                )
                sections_done.append(sect)
                yield {
                    "event": "section_done",
                    "data": json.dumps(
                        {
                            "type": "section_done",
                            "name": sect,
                            "file_id": file_id,
                        },
                        ensure_ascii=False,
                    ),
                }
            yield {
                "event": "done",
                "data": json.dumps(
                    {
                        "type": "done",
                        "total_cost_usd": total_cost,
                        "total_turns": total_turns,
                        "sections_completed": sections_done,
                    },
                    ensure_ascii=False,
                ),
            }
        finally:
            duration_ms = int((time.monotonic() - t0) * 1000)
            try:
                await asyncio.to_thread(
                    _write_run_log_sync,
                    endpoint="mine_full",
                    project_id=project_id,
                    idea=idea_text[:200],
                    num_turns=total_turns or None,
                    total_cost_usd=total_cost or None,
                    duration_ms=duration_ms,
                    stop_reason="completed" if not last_error else "error",
                    fallback_used=False,
                    error=last_error,
                    is_mock=False,
                )
                # v0.21: 预算告警（写完 log 立即对账）
                await asyncio.to_thread(update_after_run, "mine_full")
            except Exception as exc:  # noqa: BLE001
                logger.warning("mine_full agent_run_log write failed: %s", exc)
            release_sse_slot("mine_full")

    return EventSourceResponse(gen())


# ─── v0.34: detached agent runs (持久化 events，断线可恢复) ──────────────────


_DEFAULT_FULL_SECTIONS_RUNS = list(_DEFAULT_FULL_SECTIONS)


class StartRunRequest(BaseModel):
    endpoint: str                                     # 'mine_full' | 'mine_spike'
    project_id: str | None = None
    idea: str
    max_turns: int | None = 8
    sections: list[str] | None = None                 # 仅 mine_full 用


def _new_run_id() -> str:
    return f"r-{uuid.uuid4().hex[:12]}"


def _persist_event_sync(run_id: str, project_id: str | None, seq: int, ev: dict) -> None:
    """短事务把一个 event 写到 agent_events。失败仅 log，不抛。"""
    db = SessionLocal()
    try:
        row = AgentEvent(
            run_id=run_id,
            project_id=project_id,
            seq=seq,
            type=str(ev.get("type") or "message")[:32],
            payload=ev,
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("persist_event failed run=%s seq=%s", run_id, seq, exc_info=True)
    finally:
        db.close()


def _update_run_sync(run_id: str, **fields) -> None:
    db = SessionLocal()
    try:
        row = db.get(AgentRun, run_id)
        if not row:
            return
        for k, v in fields.items():
            setattr(row, k, v)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("update_run failed run=%s", run_id, exc_info=True)
    finally:
        db.close()


def _read_run_status_sync(run_id: str) -> str | None:
    db = SessionLocal()
    try:
        row = db.get(AgentRun, run_id)
        return row.status if row else None
    finally:
        db.close()


async def _run_mining_in_background(
    run_id: str,
    *,
    endpoint: str,
    project_id: str | None,
    idea: str,
    max_turns: int,
    sections: list[str] | None,
) -> None:
    """后端独立 task；客户端断不断都跑到底，每个 event 落 DB。"""
    seq = 0
    total_cost = 0.0
    total_turns = 0
    last_error: str | None = None
    cancelled = False

    snap = PlanSnapshotState(project_id, run_id, endpoint) if project_id else None

    async def _emit(ev: dict) -> bool:
        """落一条 event；返 False 说明检测到 cancel，应停止。"""
        nonlocal seq
        seq += 1
        await asyncio.to_thread(_persist_event_sync, run_id, project_id, seq, ev)
        if snap:
            await asyncio.to_thread(feed_plan_snapshot, snap, ev, seq)
            if ev.get("type") in ("tool_use", "tool_result", "done", "section_done"):
                db = SessionLocal()
                try:
                    await asyncio.to_thread(snap.flush, db)
                finally:
                    db.close()
        # 每条 event 后顺手 check cancel（轻量：单次主键查询）
        st = await asyncio.to_thread(_read_run_status_sync, run_id)
        return st == "running"

    t0 = time.monotonic()
    try:
        # SSE 槽位 + 预算（与老路径一致；mine_spike / mine_full 共享同一池）
        try:
            ensure_not_blocked()
        except BudgetBlocked as exc:
            await _emit({"type": "error", "message": f"今日预算超限：${exc.daily_sum:.4f}"})
            last_error = "budget_blocked"
            return

        slot_label = endpoint  # 'mine_spike'|'mine_full'
        try:
            await acquire_sse_slot(slot_label)
        except SSEBusy:
            await _emit({"type": "error", "message": "服务繁忙，请稍候"})
            last_error = "sse_busy"
            return

        try:
            if endpoint == "mine_spike":
                async for ev in agent_mine_stream(
                    idea, max_turns=max_turns, endpoint="mine_spike", project_id=project_id,
                ):
                    if not await _emit(ev):
                        cancelled = True
                        break
                    etype = ev.get("type")
                    if etype == "done":
                        if ev.get("total_cost_usd"):
                            total_cost += float(ev["total_cost_usd"])
                        if ev.get("num_turns"):
                            total_turns += int(ev["num_turns"])
                    elif etype == "error":
                        last_error = ev.get("message")
            elif endpoint == "mine_full":
                if not project_id:
                    await _emit({"type": "error", "message": "mine_full 需要 project_id"})
                    last_error = "missing_project_id"
                    return
                # 加载项目 / 域名 label
                p_db = SessionLocal()
                try:
                    p = p_db.get(Project, project_id)
                    if not p:
                        await _emit({"type": "error", "message": f"project {project_id} not found"})
                        last_error = "project_not_found"
                        return
                    title = p.title or "未命名项目"
                    domain_label = p.custom_domain or _DOMAIN_LABEL.get(p.domain or "", p.domain or "其他")
                finally:
                    p_db.close()

                sects = sections or list(_DEFAULT_FULL_SECTIONS_RUNS)
                for sect in sects:
                    if cancelled:
                        break
                    if not await _emit({"type": "section_start", "name": sect}):
                        cancelled = True
                        break
                    sect_md_parts: list[str] = []
                    async for ev in agent_section_demo.mine_section_via_agent(
                        sect,
                        {
                            "idea_text": idea,
                            "title": title,
                            "domain": domain_label,
                            "project_id": project_id,
                        },
                    ):
                        if not await _emit(ev):
                            cancelled = True
                            break
                        etype = ev.get("type")
                        if etype == "delta":
                            sect_md_parts.append(ev.get("text", ""))
                        elif etype == "done":
                            if ev.get("total_cost_usd"):
                                total_cost += float(ev["total_cost_usd"])
                            if ev.get("num_turns"):
                                total_turns += int(ev["num_turns"])
                        elif etype == "error":
                            last_error = ev.get("message")
                    if cancelled:
                        break
                    file_id = await asyncio.to_thread(
                        _write_full_section, project_id, sect, "".join(sect_md_parts),
                    )
                    if not await _emit({"type": "section_done", "name": sect, "file_id": file_id}):
                        cancelled = True
                        break
            else:
                await _emit({"type": "error", "message": f"unknown endpoint {endpoint}"})
                last_error = f"unknown endpoint {endpoint}"
                return

            if not cancelled:
                await _emit({
                    "type": "done",
                    "total_cost_usd": total_cost,
                    "total_turns": total_turns,
                })
        finally:
            release_sse_slot(slot_label)
    except asyncio.CancelledError:
        cancelled = True
        try:
            await _emit({"type": "error", "message": "task cancelled"})
        except Exception:
            pass
        raise
    except Exception as exc:  # noqa: BLE001
        last_error = f"{type(exc).__name__}: {exc}"
        logger.exception("agent run %s failed", run_id)
        try:
            await _emit({"type": "error", "message": last_error})
        except Exception:
            pass
    finally:
        # 终态写回 AgentRun
        if cancelled:
            final_status = "cancelled"
        elif last_error:
            final_status = "error"
        else:
            final_status = "completed"
        await asyncio.to_thread(
            _update_run_sync,
            run_id,
            status=final_status,
            finished_at=_dt.datetime.now(_tz.utc),
            total_cost_usd=total_cost or None,
            num_turns=total_turns or None,
            error=last_error,
        )
        # 断点续作：finalize snap + dump jsonl
        if snap:
            def _finalize_snap():
                db = SessionLocal()
                try:
                    snap.finalize(db, final_status)
                finally:
                    db.close()
            try:
                await asyncio.to_thread(_finalize_snap)
            except Exception as _exc:  # noqa: BLE001
                logger.warning("plan_snapshot finalize failed: %s", _exc)
        try:
            await asyncio.to_thread(dump_and_purge_events_sync, run_id, project_id)
        except Exception as _exc:  # noqa: BLE001
            logger.warning("dump_and_purge_events failed: %s", _exc)
        # 兼容老 AgentRunLog
        try:
            duration_ms = int((time.monotonic() - t0) * 1000)
            await asyncio.to_thread(
                _write_run_log_sync,
                endpoint=endpoint,
                project_id=project_id,
                idea=idea[:200],
                num_turns=total_turns or None,
                total_cost_usd=total_cost or None,
                duration_ms=duration_ms,
                stop_reason=final_status,
                fallback_used=False,
                error=last_error,
                is_mock=False,
            )
            await asyncio.to_thread(update_after_run, endpoint)
        except Exception as _exc:  # noqa: BLE001
            logger.warning("agent_run_log write failed: %s", _exc)


# 后台 task registry（弱引用一下；FastAPI 进程内单实例）
_BG_TASKS: dict[str, asyncio.Task] = {}


@router.post("/runs/start")
async def start_run(body: StartRunRequest):
    if body.endpoint not in ("mine_spike", "mine_full"):
        raise HTTPException(400, f"unsupported endpoint {body.endpoint}")
    idea = (body.idea or "").strip()
    if not idea:
        raise HTTPException(400, "idea 为空")
    if body.endpoint == "mine_full" and not body.project_id:
        raise HTTPException(400, "mine_full 需要 project_id")

    run_id = _new_run_id()
    db = SessionLocal()
    try:
        row = AgentRun(
            id=run_id,
            project_id=body.project_id,
            endpoint=body.endpoint,
            status="running",
            idea=idea[:4000],
        )
        db.add(row)
        db.commit()
    finally:
        db.close()

    task = asyncio.create_task(_run_mining_in_background(
        run_id,
        endpoint=body.endpoint,
        project_id=body.project_id,
        idea=idea,
        max_turns=int(body.max_turns or 8),
        sections=body.sections,
    ))
    _BG_TASKS[run_id] = task

    def _cleanup(_t: asyncio.Task) -> None:
        _BG_TASKS.pop(run_id, None)

    task.add_done_callback(_cleanup)

    return {"run_id": run_id}


def _serialize_run(row: AgentRun) -> dict:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "endpoint": row.endpoint,
        "status": row.status,
        "idea": row.idea,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "total_cost_usd": row.total_cost_usd,
        "num_turns": row.num_turns,
        "error": row.error,
    }


@router.get("/runs/active")
def get_active_run(project_id: str = Query(...), db: Session = Depends(get_db)):
    """该项目下最新的 status='running' run（≤1 个；多个返回最新一条）。"""
    row = (
        db.query(AgentRun)
        .filter(AgentRun.project_id == project_id, AgentRun.status == "running")
        .order_by(AgentRun.started_at.desc())
        .first()
    )
    if not row:
        return None
    return _serialize_run(row)


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    row = db.get(AgentRun, run_id)
    if not row:
        raise HTTPException(404, "run not found")
    return _serialize_run(row)


@router.get("/runs/{run_id}/events")
def get_run_events(
    run_id: str,
    since: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """读 run 历史 events。run 还在跑 → 走 DB；run 已终态 → 自动 fallback 到 jsonl 文件。"""
    run_row = db.get(AgentRun, run_id)
    pid = run_row.project_id if run_row else None
    # 优先 DB（run 运行中或刚结束未 dump）；DB 为空 + 终态时自动落到 jsonl
    rows = (
        db.query(AgentEvent)
        .filter(AgentEvent.run_id == run_id, AgentEvent.seq > since)
        .order_by(AgentEvent.seq.asc())
        .limit(2000)
        .all()
    )
    if rows:
        return [
            {
                "seq": r.seq,
                "type": r.type,
                "payload": r.payload,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    # DB 空：读 jsonl FileNode
    if pid:
        return read_run_events_sync(pid, run_id, since=since)
    return []


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, db: Session = Depends(get_db)):
    row = db.get(AgentRun, run_id)
    if not row:
        raise HTTPException(404, "run not found")
    if row.status == "running":
        row.status = "cancelled"
        row.finished_at = _dt.datetime.now(_tz.utc)
        db.commit()
    # 同时尝试取消进程内 task（best-effort）
    t = _BG_TASKS.get(run_id)
    if t and not t.done():
        t.cancel()
    return {"ok": True, "status": row.status}


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, since: int = Query(0, ge=0)):
    """SSE：先吐 seq>since 已有 events，再 poll DB tail 直到 status != running。"""
    # 校验 run 存在
    db = SessionLocal()
    try:
        row = db.get(AgentRun, run_id)
        if not row:
            raise HTTPException(404, "run not found")
    finally:
        db.close()

    async def gen():
        last_seen = since
        idle_loops = 0
        while True:
            # 拉新 events
            db2 = SessionLocal()
            try:
                rows = (
                    db2.query(AgentEvent)
                    .filter(AgentEvent.run_id == run_id, AgentEvent.seq > last_seen)
                    .order_by(AgentEvent.seq.asc())
                    .limit(500)
                    .all()
                )
                run_row = db2.get(AgentRun, run_id)
                run_status = run_row.status if run_row else "error"
            finally:
                db2.close()

            for r in rows:
                payload = dict(r.payload or {})
                payload.setdefault("type", r.type)
                payload["__seq"] = r.seq
                yield {
                    "event": r.type,
                    "data": json.dumps(payload, ensure_ascii=False),
                }
                last_seen = r.seq

            if rows:
                idle_loops = 0
            else:
                idle_loops += 1

            if run_status != "running":
                # 再扫一轮没新事件就收尾
                if not rows and idle_loops >= 1:
                    yield {
                        "event": "stream_end",
                        "data": json.dumps({"type": "stream_end", "status": run_status}, ensure_ascii=False),
                    }
                    return

            await asyncio.sleep(0.2)

    return EventSourceResponse(gen())
