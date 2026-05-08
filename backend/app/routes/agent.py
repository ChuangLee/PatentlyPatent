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
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from ..agent_sdk_spike import agent_mine_stream
from .. import agent_section_demo
from ..agent_section_demo import mine_section_via_agent
from ..config import settings
from ..db import SessionLocal, get_db
from ..mining import build_prior_art_section_legacy, _DOMAIN_LABEL
from ..models import AgentRunLog, FileNode, Project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


class MineSpikeRequest(BaseModel):
    idea: str
    max_turns: int = 8


@router.post("/mine_spike")
async def mine_spike(body: MineSpikeRequest):
    async def gen():
        async for ev in agent_mine_stream(body.idea, max_turns=body.max_turns):
            yield {
                "event": ev.get("type", "message"),
                "data": json.dumps(ev, ensure_ascii=False),
            }

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
                    is_mock=not settings.use_agent_sdk_real,
                ))
                _ab_log_db.commit()
            except Exception:
                _ab_log_db.rollback()
                raise
            finally:
                _ab_log_db.close()
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
                    is_mock=not settings.use_agent_sdk_real,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("mine_full agent_run_log write failed: %s", exc)

    return EventSourceResponse(gen())
