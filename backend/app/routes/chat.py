"""对话 SSE：chat（用户对话）+ auto-mining（自动挖掘）"""
from __future__ import annotations
import asyncio
import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from ..db import get_db, session_scope
from ..models import Project, FileNode
from ..schemas import ChatRequest, AutoMineRequest, FileNodeOut
from ..llm import stream_chat, split_grapheme
from ..llm_fill import fill_section
from ..mining import build_sections
from ..research import quick_landscape, landscape_to_md

router = APIRouter(tags=["chat"])


@router.post("/projects/{pid}/chat")
async def chat_stream(pid: str, body: ChatRequest, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")

    domain_label = p.custom_domain or p.domain
    sys_prompt = (
        f"你是企业内部的专利挖掘助手。当前项目：《{p.title}》（{domain_label}）。\n"
        f"用户报门描述：{p.description}\n\n"
        "请用专业、简洁的中文回答。"
    )

    async def gen():
        yield {"event": "thinking", "data": "{}"}
        await asyncio.sleep(0.3)
        async for piece in stream_chat(body.userMsg, system=sys_prompt):
            yield {"event": "delta", "data": json.dumps({"chunk": piece}, ensure_ascii=False)}
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(gen())


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

    async def gen():
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

    return EventSourceResponse(gen())
