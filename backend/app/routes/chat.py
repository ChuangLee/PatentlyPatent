"""对话 SSE：chat（用户对话）+ auto-mining（自动挖掘）

v0.9-A 新增：
- chat 流式回答收尾时，调 answer_router.route_answer 识别用户问题归属的章节，
  把回答自动追加到 'AI 输出/' 下对应的 md 文件，并通过 SSE file 事件推给前端。
- 新增 POST /projects/:id/chat/append-to-file 显式追加端点，供前端手动触发。
"""
from __future__ import annotations
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from ..budget import BudgetBlocked, ensure_not_blocked
from ..concurrency import SSEBusy, acquire_sse_slot, release_sse_slot
from ..db import get_db, session_scope
from ..models import Project, FileNode
from ..schemas import ChatRequest, AutoMineRequest, FileNodeOut
from ..llm import stream_chat, split_grapheme
from ..llm_fill import fill_section
from ..mining import build_sections
from ..research import quick_landscape, landscape_to_md
from ..answer_router import route_answer

router = APIRouter(tags=["chat"])


# ─── 工具：把内容追加到指定 md 文件 ───────────────────────────────────────


def _format_user_supplement(user_msg: str, ai_summary: str, ts: datetime) -> str:
    """生成「💬 用户补充」block。"""
    ts_str = ts.strftime("%Y-%m-%d %H:%M")
    # 把 ai_summary 中的换行加上 markdown blockquote 前缀，避免破坏 quote 结构
    summary_lines = ai_summary.strip().splitlines() or [""]
    quoted = "\n".join(f"> {line}" if line else ">" for line in summary_lines)
    user_lines = user_msg.strip().splitlines() or [""]
    user_quoted = "\n".join(f"> {line}" if line else ">" for line in user_lines)
    return (
        f"\n\n> 💬 **用户补充**（{ts_str}）：\n"
        f"{user_quoted}\n"
        f">\n"
        f"{quoted}\n"
    )


def _append_to_section(content: str, anchor: Optional[str], block: str) -> str:
    """把 block 拼到 content 的末尾或指定 H2 anchor 之后（下一个 H2 之前）。"""
    if not anchor or anchor not in content:
        # anchor 没给或没找到：直接拼到末尾
        if not content.endswith("\n"):
            content += "\n"
        return content + block

    # 找到 anchor 行
    idx = content.find(anchor)
    # anchor 这行的结尾
    line_end = content.find("\n", idx)
    if line_end == -1:
        # anchor 是最后一行
        return content + block

    # 找下一个 H2（## ）的位置；如没有，则末尾
    rest = content[line_end:]
    # 用换行 + "## " 定位下一个 H2，避免误命中行内 ##
    next_h2_rel = rest.find("\n## ")
    if next_h2_rel == -1:
        # anchor 之后没有更多 H2 —— 拼到文末
        return content.rstrip("\n") + block + "\n"

    insert_pos = line_end + next_h2_rel
    return content[:insert_pos] + block + content[insert_pos:]


def _find_ai_md_file(db: Session, pid: str, file_name: str) -> Optional[FileNode]:
    """在该项目 'AI 输出/' 文件夹下找指定 md 文件。"""
    # 找 ai 根目录
    ai_root = db.query(FileNode).filter(
        FileNode.project_id == pid,
        FileNode.parent_id.is_(None),
        FileNode.source == "ai",
    ).first()
    if not ai_root:
        return None
    return db.query(FileNode).filter(
        FileNode.project_id == pid,
        FileNode.parent_id == ai_root.id,
        FileNode.name == file_name,
        FileNode.kind == "file",
    ).first()


def _do_append(
    db: Session,
    pid: str,
    file_name: str,
    anchor: Optional[str],
    user_msg: str,
    ai_summary: str,
) -> Optional[FileNode]:
    """实际写库，返回更新后的 FileNode（None 表示文件不存在）。"""
    f = _find_ai_md_file(db, pid, file_name)
    if not f:
        return None
    now = datetime.now(timezone.utc)
    block = _format_user_supplement(user_msg, ai_summary, now)
    new_content = _append_to_section(f.content or "", anchor, block)
    f.content = new_content
    f.size = len(new_content.encode())
    f.updated_at = now
    db.commit()
    db.refresh(f)
    return f


# ─── 路由 ────────────────────────────────────────────────────────────────


@router.post("/projects/{pid}/chat")
async def chat_stream(pid: str, body: ChatRequest, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")

    domain_label = p.custom_domain or p.domain

    # v0.11-B + v0.12-C: AI 输出/ 章节摘要 + 我的资料/ 用户上传文件摘要
    user_root = db.query(FileNode).filter(
        FileNode.project_id == pid,
        FileNode.parent_id.is_(None),
        FileNode.source == "user",
    ).first()
    user_files = []
    if user_root:
        user_files = db.query(FileNode).filter(
            FileNode.project_id == pid,
            FileNode.parent_id == user_root.id,
            FileNode.kind == "file",
        ).all()

    ai_files = db.query(FileNode).filter(
        FileNode.project_id == pid,
        FileNode.source == "ai",
        FileNode.kind == "file",
    ).order_by(FileNode.name).all()

    ai_blocks: list[str] = []
    for f in ai_files[:8]:
        snip = (f.content or "")[:600]
        if snip:
            ai_blocks.append(f"### {f.name}\n{snip}")
    ai_ctx = "\n\n".join(ai_blocks) or "（暂无 AI 已生成内容）"

    user_blocks: list[str] = []
    for f in user_files[:6]:
        if f.content:
            user_blocks.append(f"### {f.name}（用户上传）\n{f.content[:400]}")
        elif f.url:
            user_blocks.append(f"- {f.name}（链接：{f.url}）")
        else:
            user_blocks.append(f"- {f.name}（{f.mime or '二进制'} · {f.size or '?'} bytes）")
    user_ctx = "\n\n".join(user_blocks) or "（用户暂未上传辅助资料）"

    sys_prompt = (
        f"你是企业内部的专利挖掘助手。当前项目：《{p.title}》（{domain_label}）。\n"
        f"用户报门描述：{p.description}\n\n"
        "─── 已生成的交底书章节摘要（基于此回答用户问题，保持上下文连贯）───\n"
        f"{ai_ctx}\n"
        "─── AI 章节摘要结束 ───\n\n"
        "─── 用户上传的辅助资料（"
        f"{len(user_files)} 项 · 最多取前 6）───\n"
        f"{user_ctx}\n"
        "─── 用户资料结束 ───\n\n"
        "请用专业、简洁的中文回答；优先引用上述章节中的具体内容与用户资料；"
        "回答末尾如有可写回的具体信息（实验数据/替代方案/资料链接），用一行"
        "「✅ 建议归档：...」总结。"
    )
    user_msg = body.userMsg or ""

    # v0.21: 预算硬阻断 + SSE 并发限流
    try:
        ensure_not_blocked()
    except BudgetBlocked as exc:
        raise HTTPException(503, f"今日预算已超限：${exc.daily_sum:.4f}")
    try:
        await acquire_sse_slot("chat")
    except SSEBusy:
        raise HTTPException(503, "服务繁忙，请稍候")

    async def gen():
        try:
            yield {"event": "thinking", "data": "{}"}
            await asyncio.sleep(0.3)

            # 收集 LLM 完整回答用于追加（前端仍按 chunk 流式渲染）
            full_answer_chunks: list[str] = []
            async for piece in stream_chat(user_msg, system=sys_prompt):
                full_answer_chunks.append(piece)
                yield {"event": "delta", "data": json.dumps({"chunk": piece}, ensure_ascii=False)}

            full_answer = "".join(full_answer_chunks).strip()

            # ── 章节路由 + 写回 ─────────────────────────────────────
            target = route_answer(user_msg)
            if target and full_answer:
                try:
                    with session_scope() as db2:
                        updated = _do_append(
                            db2, pid,
                            file_name=target["file"],
                            anchor=target.get("anchor"),
                            user_msg=user_msg,
                            ai_summary=full_answer,
                        )
                        if updated is not None:
                            node_out = FileNodeOut.model_validate(updated).model_dump(by_alias=True)
                            # 通知前端：已经把回答归档进文件
                            notice = f"\n\n📎 已把这条回答归档到 AI 输出/{target['file']}。\n"
                            for chunk in split_grapheme(notice, 3):
                                yield {"event": "delta", "data": json.dumps({"chunk": chunk}, ensure_ascii=False)}
                            yield {"event": "file", "data": json.dumps({"node": node_out, "category": target.get("category")}, ensure_ascii=False)}
                except Exception as e:
                    err_note = f"\n\n⚠️ 归档失败：{type(e).__name__}: {e}\n"
                    for chunk in split_grapheme(err_note, 3):
                        yield {"event": "delta", "data": json.dumps({"chunk": chunk}, ensure_ascii=False)}

            yield {"event": "done", "data": "{}"}
        finally:
            release_sse_slot("chat")

    return EventSourceResponse(gen())


# ─── 显式追加端点 ────────────────────────────────────────────────────────


class AppendToFileBody(BaseModel):
    fileName: str
    sectionAnchor: Optional[str] = None
    content: str
    userMsg: str


@router.post("/projects/{pid}/chat/append-to-file", response_model=dict)
def append_to_file(pid: str, body: AppendToFileBody, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    updated = _do_append(
        db, pid,
        file_name=body.fileName,
        anchor=body.sectionAnchor,
        user_msg=body.userMsg,
        ai_summary=body.content,
    )
    if updated is None:
        raise HTTPException(404, f"file not found in AI 输出/: {body.fileName}")
    return FileNodeOut.model_validate(updated).model_dump(by_alias=True)


# ─── auto-mining（保持原状）─────────────────────────────────────────────


@router.post("/projects/{pid}/auto-mining")
async def auto_mining(pid: str, body: AutoMineRequest, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")

    ai_root_id = body.aiRootId
    if not ai_root_id:
        ai_root = db.query(FileNode).filter(
            FileNode.project_id == pid,
            FileNode.parent_id.is_(None),
            FileNode.source == "ai",
        ).first()
        if not ai_root:
            raise HTTPException(404, "AI root folder not found")
        ai_root_id = ai_root.id

    ctx = {
        "title": p.title,
        "domain": p.domain,
        "customDomain": p.custom_domain,
        "description": p.description,
        "intake": p.intake_json,
    }
    sections = build_sections(ctx)

    # v0.21: 预算硬阻断 + SSE 并发限流
    try:
        ensure_not_blocked()
    except BudgetBlocked as exc:
        raise HTTPException(503, f"今日预算已超限：${exc.daily_sum:.4f}")
    try:
        await acquire_sse_slot("auto_mining")
    except SSEBusy:
        raise HTTPException(503, "服务繁忙，请稍候")

    async def gen():
      try:
        yield {"event": "thinking", "data": "{}"}
        await asyncio.sleep(0.3)

        opening = (
            f"📋 收到，我先把你的报门描述读一遍...\n\n"
            f"标题：{p.title}\n领域：{p.custom_domain or p.domain}\n\n"
            "开始自动挖掘——能写的我直接写好放到 AI 输出/，不清楚的我会列出来请你回答。\n\n"
        )
        for chunk in split_grapheme(opening, 3):
            yield {"event": "delta", "data": json.dumps({"chunk": chunk}, ensure_ascii=False)}
            await asyncio.sleep(0.025)

        # ─── 第 0 步：调智慧芽看下该领域的存量（mid-fi 真接 ↗） ───
        sniff = "\n🔎 先去智慧芽快速看看该方向已经有多少专利申请...\n"
        for chunk in split_grapheme(sniff, 3):
            yield {"event": "delta", "data": json.dumps({"chunk": chunk}, ensure_ascii=False)}
            await asyncio.sleep(0.02)
        landscape = await quick_landscape(p.description, p.title)
        landscape_md = landscape_to_md(landscape)
        if landscape.get("available"):
            note = (
                f"   ✓ 已检索：综合命中 {landscape.get('total_count', 0):,} 篇\n"
                f"   ✓ 关键词：{', '.join(landscape.get('keywords', [])[:5])}\n"
            )
        else:
            note = f"   ⚠️ 智慧芽未跑通：{landscape.get('error', '未知')}\n"
        for chunk in split_grapheme(note, 3):
            yield {"event": "delta", "data": json.dumps({"chunk": chunk}, ensure_ascii=False)}
            await asyncio.sleep(0.015)
        # 把 landscape 注入到第一节顶部
        if sections and sections[0]["name"] == "01-背景技术.md":
            sections[0]["content"] = landscape_md + sections[0]["content"]

        for sec in sections:
            intro = (
                f"\n✍️ 正在写「{sec['name'].replace('.md', '')}」...\n"
                if sec["phase"] == "auto"
                else f"\n📌 已生成「问题清单」，请看左侧 AI 输出/{sec['name']}\n"
            )
            for chunk in split_grapheme(intro, 3):
                yield {"event": "delta", "data": json.dumps({"chunk": chunk}, ensure_ascii=False)}
                await asyncio.sleep(0.02)
            await asyncio.sleep(0.3)

            # 用 LLM（或 mock）填占位
            filled = await fill_section(sec["content"], ctx)

            # 把文件真持久化到数据库
            with session_scope() as db2:
                fid = f"f-{uuid.uuid4().hex[:10]}"
                now = datetime.now(timezone.utc)
                db2.add(FileNode(
                    id=fid, project_id=pid, name=sec["name"], kind="file",
                    parent_id=ai_root_id, source="ai",
                    mime="text/markdown",
                    content=filled,
                    size=len(filled.encode()),
                    created_at=now, updated_at=now,
                ))

            # 给前端发 file 事件
            node_out = {
                "id": fid, "name": sec["name"], "kind": "file",
                "parentId": ai_root_id, "source": "ai", "hidden": False,
                "mime": "text/markdown", "content": filled,
                "size": len(filled.encode()),
                "createdAt": now.isoformat(), "updatedAt": now.isoformat(),
            }
            yield {"event": "file", "data": json.dumps({"node": node_out}, ensure_ascii=False)}
            await asyncio.sleep(0.4)

            tick = f"   ✓ 已落到 AI 输出/{sec['name']}\n"
            for chunk in split_grapheme(tick, 3):
                yield {"event": "delta", "data": json.dumps({"chunk": chunk}, ensure_ascii=False)}
                await asyncio.sleep(0.015)

        # 项目状态更新
        with session_scope() as db2:
            p2 = db2.get(Project, pid)
            if p2 and p2.status == "drafting":
                p2.status = "researching"

        wrap = (
            "\n✅ 自动挖掘完成。\n\n"
            "你看下左侧文件树新冒出来的几个 md 文件——\n"
            "  · 1~6 节是 AI 自动写的初稿，可点开右侧预览，有不准的告诉我改\n"
            "  · _问题清单.md 是 AI 自己回答不了的几条，挑感兴趣的在下方回答即可\n\n"
            "等你确认 / 补充完，我把所有章节合并生成完整的 .docx 交底书放到 AI 输出/专利交底书.docx。\n"
        )
        for chunk in split_grapheme(wrap, 3):
            yield {"event": "delta", "data": json.dumps({"chunk": chunk}, ensure_ascii=False)}
            await asyncio.sleep(0.02)

        yield {"event": "done", "data": "{}"}
      finally:
        release_sse_slot("auto_mining")

    return EventSourceResponse(gen())
