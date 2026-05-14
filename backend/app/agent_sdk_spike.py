"""Claude Agent SDK 走专利挖掘单端点 — in-process MCP server 装配。

提供 in-process MCP server 给 agent_interview / agent_section_demo 等路径复用：
  - update_plan         agent 工作表
  - generate_disclosure docx 导出
  - file_write_section  把 markdown 写到 project 文件树
  - save_research       调研重要素材落「AI 输出/调研下载/<分类>/」
  - read_user_file      读项目里任意文件（含项目计划.md 等 AI 自己的产出）
  - file_search_in_project  在项目内模糊搜文件
  - search_kb / read_kb_file 专利知识库（419 篇 CN 实务）

智慧芽数据由 agent_interview.py 装配的远程 MCP server（A 路托管 MCP 19 工具）
负责，本模块不再注入老 in-house REST 工具（套餐欠费后总返 67200005）。
BigQuery 降级备选见 patents_bq.py。

对外 yield 事件：thinking / tool_use / tool_result / delta / file / done / error。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from .config import settings
from . import zhihuiya
from .zhihuiya import ZhihuiyaError

logger = logging.getLogger(__name__)


def _safe_tool_error(label: str, exc: Exception, q: str | None = None) -> dict:
    """v0.20 Wave1：tool 内统一兜底返回，绝不冒泡 SDK 让 turn 失败。

    分支：
      - ZhihuiyaError：业务/降级失败，给 LLM 一段简明提示
      - 其它 Exception：吞掉异常细节，回 isError=True
    """
    if isinstance(exc, ZhihuiyaError):
        msg = f"{label} 智慧芽业务失败（已降级），原因：{exc}"
    else:
        msg = f"{label} 失败：{type(exc).__name__}: {exc}"
    qpreview = (q or "").strip().replace("\n", " ")[:50]
    logger.warning("tool %s err q='%s' %s", label, qpreview, msg)
    return {"content": [{"type": "text", "text": msg}], "isError": True}


def log_startup_status() -> None:
    """由 main.py 在 lifespan startup 阶段调用一次。

    放在 import 顶层调用会被 logging.basicConfig 之前的 root handler 吞掉，
    所以延迟到 logging 初始化完成后再打。
    """
    from .config import assert_claude_cli_available
    cli_path = assert_claude_cli_available()
    logger.info(
        "agent_sdk_spike: claude_cli=%s use_real_zhihuiya=%s model=%s",
        cli_path,
        settings.use_real_zhihuiya,
        settings.anthropic_model,
    )


SYSTEM_PROMPT = (
    "你是一名资深专利挖掘助手。用户给出一段技术构思，"
    "你需要：\n"
    "1) 把构思拆成核心技术关键词；\n"
    "2) 调用 patsnap_search / suggest_keywords 等智慧芽托管 MCP 工具做检索"
    "（关键词扩展 + 命中专利列表 + 申请人/趋势/分类号）；A 路返业务错时自动"
    "切 bq_search_patents（Google Patents BigQuery 免费降级）。\n"
    "3) 必要时用 file_search_in_project 在项目已有文件里搜历史素材；\n"
    "4) 综合判断新颖性、技术热度、主要竞争对手；\n"
    "5) 给出 3-5 条可挖掘的差异化角度；\n"
    "6) 必要时调用 file_write_section 把分析结论写回项目（仅在用户明确要求"
    "保存或调用方传入 project_id 时才写）。\n"
    "7) 调研中遇到与本创意高度相关的素材（类似已有专利 / 重要论文博客），"
    "调用 save_research(category='similar_patent'|'related_article'|'note') "
    "把要点摘要保存到「AI 输出/调研下载/<分类>/」下，便于员工查阅。\n"
    "保持简洁，工具调用次数不超过 8 次。最后用中文给出结论。"
)


# ─── tool 定义（仅在 SDK 真实调用时使用） ──────────────────────────────────────

def _build_mcp_server():
    """延迟构造，只有在真实 SDK 路径下才需要。

    返回 (server, tool_names) 二元组，便于注册到 ClaudeAgentOptions。
    """
    from claude_agent_sdk import tool, create_sdk_mcp_server

    @tool(
        "file_write_section",
        (
            "把一段 markdown 写到指定 project 的文件树下的 AI 输出文件夹（默认 'AI 输出'）。"
            "若 project 不存在或文件夹找不到，会返回 isError 并说明原因。"
            "name 是新建 markdown 文件的名字（自动补 .md）。"
        ),
        {"project_id": str, "name": str, "content": str, "parent_folder": str},
    )
    async def file_write_section(args: dict[str, Any]) -> dict:
        try:
            return await _do_file_write_section(
                project_id=(args or {}).get("project_id", ""),
                name=(args or {}).get("name", ""),
                content=(args or {}).get("content", ""),
                parent_folder=(args or {}).get("parent_folder") or "AI 输出",
            )
        except ZhihuiyaError as exc:
            return _safe_tool_error("file_write_section", exc)
        except Exception as exc:  # noqa: BLE001
            return _safe_tool_error("file_write_section", exc)

    @tool(
        "save_research",
        (
            "调研过程中遇到非常重要的素材（与本创意高度相关的论文/博客/类似已有专利等），"
            "调用此工具把要点摘要保存到项目文件树「AI 输出/调研下载/<分类>/」下，"
            "便于员工后续查阅。category 限定取值："
            "'similar_patent'（类似已有专利，含公开号 / 申请人 / 与本案差异）、"
            "'related_article'（相关文章 / 论文 / 博客，含来源链接和核心结论）、"
            "'note'（其他笔记，调研中临时记录）。"
            "name 是文件名（自动补 .md）；content 是 markdown 摘要；"
            "source_url 可选，若有抓取/查到的原文链接请填上。"
        ),
        {
            "project_id": str,
            "name": str,
            "content": str,
            "category": str,
            "source_url": str,
        },
    )
    async def save_research(args: dict[str, Any]) -> dict:
        try:
            return await _do_save_research(
                project_id=(args or {}).get("project_id", ""),
                name=(args or {}).get("name", ""),
                content=(args or {}).get("content", ""),
                category=(args or {}).get("category") or "note",
                source_url=(args or {}).get("source_url") or "",
            )
        except Exception as exc:  # noqa: BLE001
            return _safe_tool_error("save_research", exc)

    @tool(
        "file_search_in_project",
        (
            "在指定 project 文件树下按关键字模糊搜文件正文（content LIKE '%keyword%'，"
            "kind='file'）。覆盖「我的资料/」「AI 输出/」两个文件夹。"
            "返回最多 5 条命中 [{file_id, name, snippet}]，snippet 是 keyword 前后 80 字截取。"
        ),
        {"project_id": str, "keyword": str},
    )
    async def file_search_in_project(args: dict[str, Any]) -> dict:
        try:
            return await _do_file_search_in_project(
                project_id=(args or {}).get("project_id", ""),
                keyword=(args or {}).get("keyword", ""),
            )
        except ZhihuiyaError as exc:
            return _safe_tool_error("file_search_in_project", exc)
        except Exception as exc:  # noqa: BLE001
            return _safe_tool_error("file_search_in_project", exc)

    @tool(
        "read_user_file",
        (
            "按文件名读项目中任意文件的正文。常用于读「我的资料/」下用户上传的资料、"
            "或读「AI 输出/项目计划.md」拿上次工作进度。"
            "支持格式：PDF / Word .docx / PowerPoint .pptx / Excel .xlsx/.xls / "
            "Markdown / 纯文本 / JSON / CSV。"
            "（.doc/.ppt 老二进制格式暂不支持，需另存为新格式）。"
            "name 是文件名（如 'AI和身份认证.pptx' 或 '项目计划.md'）。返回 content 文本（最多 30000 字）。"
        ),
        {"project_id": str, "name": str},
    )
    async def read_user_file(args: dict[str, Any]) -> dict:
        try:
            return await _do_read_user_file(
                project_id=(args or {}).get("project_id", ""),
                name=(args or {}).get("name", ""),
            )
        except Exception as exc:  # noqa: BLE001
            return _safe_tool_error("read_user_file", exc)

    @tool(
        "search_kb",
        (
            "查项目内置的「专利知识库」（refs/专利专家知识库/ 下 419 篇 md，含 CNIPA 审查指南、"
            "知乎案例、复审无效案例、IPRdaily 等专家文章）。按关键字模糊匹配文件名 + 正文，"
            "返回 top 5 命中 [{path, title, snippet}]。"
            "适合查 CN 实务、审查指南条款、OA 答辩范式、判例等。"
        ),
        {"keyword": str},
    )
    async def search_kb(args: dict[str, Any]) -> dict:
        try:
            return await _do_search_kb(keyword=(args or {}).get("keyword", ""))
        except Exception as exc:  # noqa: BLE001
            return _safe_tool_error("search_kb", exc)

    @tool(
        "read_kb_file",
        (
            "读专利知识库中某个具体文件的完整内容。path 是相对 refs/专利专家知识库/ 的路径"
            "（如 'CNIPA_审查指南2025修改/第二部分第十章.md'）。返回 markdown 内容（最多 30000 字）。"
        ),
        {"path": str},
    )
    async def read_kb_file(args: dict[str, Any]) -> dict:
        try:
            return await _do_read_kb_file(path=(args or {}).get("path", ""))
        except Exception as exc:  # noqa: BLE001
            return _safe_tool_error("read_kb_file", exc)

    @tool(
        "generate_disclosure",
        (
            "按 No.34 模板生成专利交底书 .docx 并落到「AI 输出/专利交底书.docx」。"
            "**何时调**：(1) 您判断挖掘已经充分、可以出文档了（即等同 `[READY_FOR_DOCX]` 信号）；"
            "(2) 申请人在 chat 里说『出 docx / 生成交底书 / 给我交底书』等明确指令。"
            "工具内部会自动抓 0-报门.md + mineFull 5 节 + 上传文件 + 调研下载，按 9 章模板填充。"
            "调用前请在 chat 简短说一句『我现在出 docx』让申请人有预期；"
            "调用后系统会自动把 .docx 节点 push 到前端文件树。"
        ),
        {"project_id": str},
    )
    async def generate_disclosure(args: dict[str, Any]) -> dict:
        try:
            return await _do_generate_disclosure(
                project_id=(args or {}).get("project_id", ""),
            )
        except Exception as exc:  # noqa: BLE001
            return _safe_tool_error("generate_disclosure", exc)

    @tool(
        "update_plan",
        (
            "声明 / 更新你当前轮的工作计划，让申请人在 chat 看到你的 TODO 列表与进度。"
            "steps_json 是 JSON 字符串，形如 "
            '\'[{"id":"s1","title":"查智慧芽 X.509+智能体 命中量","status":"in_progress"},'
            '{"id":"s2","title":"读用户上传 PDF","status":"pending"}]\'。'
            "status 取值：pending / in_progress / completed / failed。"
            "每个 step 还可选两个字段："
            '"artifact_files":[\'AI 输出/调研下载/类似专利/CN121xxx.md\']（如果你刚完成这一步并产生了文件，可显式声明）'
            '；"artifact_summary":"提取出 3 个关键技术点：..."（这一步的核心结论，简短一句话）。'
            "**通常不必填** artifact_files —— 后端会根据这一步期间你调用 file_write_section / save_research 自动归属。"
            "**铁律**：(1) 任何需要 ≥2 步的工作，开始前必须调一次声明计划；"
            "(2) 每步开始或完成时调一次更新状态；(3) 在最终交付前所有步骤应为 completed/failed；"
            "(4) 续作模式下：保留已 completed 的 step id/title/status 不变，只推进待办部分。"
            "前端会把它渲染为一个 in-place 更新的 Plan 卡片（不会每次都新建卡片）。"
        ),
        {"steps_json": str},
    )
    async def update_plan(args: dict[str, Any]) -> dict:
        # no-op 服务端不需要做啥；前端 tool_use 事件里 input 已含 steps
        # 但要 echo 回 input 便于 LLM 自己回看
        try:
            import json as _json
            raw = (args or {}).get("steps_json", "") or "[]"
            steps = _json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(steps, list):
                steps = []
            n = len(steps)
            n_done = sum(1 for s in steps if isinstance(s, dict) and s.get("status") == "completed")
            n_run = sum(1 for s in steps if isinstance(s, dict) and s.get("status") == "in_progress")
            text = f"计划已更新：{n} 步，已完成 {n_done}，进行中 {n_run}。"
            return {"content": [{"type": "text", "text": text}], "data": steps}
        except Exception as exc:  # noqa: BLE001
            return _safe_tool_error("update_plan", exc)

    # v0.38 Option B: 注入 BigQuery 工具（缺凭证时优雅 skip）
    from .patents_bq import build_bq_tools_for_server
    bq_tools, bq_allowed = build_bq_tools_for_server()

    server = create_sdk_mcp_server(
        name="patent-tools",
        version="0.9.0",
        tools=[
            update_plan,
            generate_disclosure,
            file_write_section,
            save_research,
            file_search_in_project,
            read_user_file,
            search_kb,
            read_kb_file,
        ] + bq_tools,
    )
    allowed = [
        "mcp__patent-tools__update_plan",
        "mcp__patent-tools__generate_disclosure",
        "mcp__patent-tools__file_write_section",
        "mcp__patent-tools__save_research",
        "mcp__patent-tools__file_search_in_project",
        "mcp__patent-tools__read_user_file",
        "mcp__patent-tools__search_kb",
        "mcp__patent-tools__read_kb_file",
    ] + bq_allowed
    return server, allowed


# ─── file_search_in_project 业务实现 ─────────────────────────────────────────


async def _do_file_search_in_project(*, project_id: str, keyword: str) -> dict:
    if not project_id:
        return {
            "content": [{"type": "text", "text": "project_id 为空"}],
            "isError": True,
        }
    if not keyword:
        return {
            "content": [{"type": "text", "text": "keyword 为空"}],
            "isError": True,
        }

    def _sync_search() -> list[dict]:
        from .db import SessionLocal
        from .models import FileNode

        db = SessionLocal()
        try:
            like = f"%{keyword}%"
            rows = (
                db.query(FileNode)
                .filter(
                    FileNode.project_id == project_id,
                    FileNode.kind == "file",
                    FileNode.content.like(like),
                )
                .limit(5)
                .all()
            )
            results: list[dict] = []
            for r in rows:
                snippet = ""
                if r.content:
                    idx = r.content.find(keyword)
                    if idx >= 0:
                        start = max(0, idx - 80)
                        end = min(len(r.content), idx + len(keyword) + 80)
                        snippet = r.content[start:end]
                    else:
                        snippet = r.content[:160]
                results.append({
                    "file_id": r.id,
                    "name": r.name,
                    "snippet": snippet,
                })
            return results
        finally:
            db.close()

    try:
        results = await asyncio.to_thread(_sync_search)
    except Exception as exc:  # noqa: BLE001
        return {
            "content": [{"type": "text", "text": f"检索失败：{exc}"}],
            "isError": True,
        }
    text = (
        f'project={project_id} 关键字 "{keyword}" 命中 {len(results)} 个文件:\n'
        + json.dumps(results, ensure_ascii=False)
    )
    return {
        "content": [{"type": "text", "text": text}],
        "data": results,
    }


# ─── read_user_file 业务实现 ────────────────────────────────────────────────


async def _do_read_user_file(*, project_id: str, name: str) -> dict:
    """按文件名读 FileNode.content；
    v0.37: 二进制（PDF/pptx/docx）若 DB 没存 text，去 storage 读 binary 现场提文本 + 回写缓存。
    """
    if not project_id or not name:
        return {
            "content": [{"type": "text", "text": "project_id 或 name 为空"}],
            "isError": True,
        }

    def _sync_read() -> dict:
        from .db import SessionLocal
        from .models import FileNode
        from .file_extract import can_extract, extract_text
        from .config import settings as _settings
        from pathlib import Path as _P
        from datetime import datetime, timezone

        db = SessionLocal()
        try:
            row = (
                db.query(FileNode)
                .filter(
                    FileNode.project_id == project_id,
                    FileNode.kind == "file",
                    FileNode.name == name,
                )
                .first()
            )
            if row is None:
                return {"ok": False, "msg": f"文件 '{name}' 在项目 {project_id} 中未找到"}
            content = row.content or ""

            # 没文本但是支持提取的二进制 → 现场提
            if not content and can_extract(row.mime, row.name):
                # storage 路径：storage/uploads/<pid>/<fid>/<name>
                bin_path = _P(_settings.storage_root) / "uploads" / project_id / row.id / row.name
                text = extract_text(bin_path, row.mime, row.name)
                if text:
                    content = text
                    # 回写 DB 缓存，下次直接读 content
                    row.content = content
                    row.updated_at = datetime.now(timezone.utc)
                    db.commit()

            if not content:
                return {
                    "ok": False,
                    "msg": (
                        f"文件 '{name}' 是 {row.mime} ({row.size} bytes)，"
                        f"未能提取文本（可能是图片型 PDF 或不支持的格式）。"
                        f"可用 file_search_in_project 跨文件搜关键字，或让用户在 chat 里贴关键段落。"
                    ),
                }
            return {
                "ok": True,
                "name": row.name,
                "mime": row.mime,
                "size": row.size,
                "content": content[:30000],
                "truncated": len(content) > 30000,
            }
        finally:
            db.close()

    res = await asyncio.to_thread(_sync_read)
    if not res.get("ok"):
        return {"content": [{"type": "text", "text": res.get("msg", "?")}], "isError": True}
    body = (
        f"文件 {res['name']} ({res['mime']}, {res['size']} bytes):\n\n{res['content']}"
        + ("\n\n…(已截断到前 30000 字)" if res.get("truncated") else "")
    )
    return {"content": [{"type": "text", "text": body}]}


# ─── search_kb / read_kb_file 业务实现 ──────────────────────────────────────


_KB_ROOT_CACHE = None


def _get_kb_root() -> "Path":
    global _KB_ROOT_CACHE
    if _KB_ROOT_CACHE is None:
        from pathlib import Path
        from .config import PROJECT_ROOT
        _KB_ROOT_CACHE = (PROJECT_ROOT / "refs" / "专利专家知识库").resolve()
    return _KB_ROOT_CACHE


async def _do_search_kb(*, keyword: str) -> dict:
    """扫 refs/专利专家知识库/ 下 .md 文件，按文件名 + 正文模糊匹配。"""
    if not keyword or not keyword.strip():
        return {"content": [{"type": "text", "text": "keyword 为空"}], "isError": True}

    keyword = keyword.strip()

    def _sync_scan() -> list[dict]:
        from pathlib import Path
        kb_root = _get_kb_root()
        if not kb_root.exists():
            return []
        kw_lower = keyword.lower()
        results: list[dict] = []
        for md in kb_root.rglob("*.md"):
            try:
                rel = md.relative_to(kb_root).as_posix()
            except ValueError:
                continue
            score = 0
            snippet = ""
            # 文件名/路径命中权重高
            if kw_lower in rel.lower():
                score += 10
            try:
                text = md.read_text(encoding="utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                continue
            text_lower = text.lower()
            idx = text_lower.find(kw_lower)
            if idx >= 0:
                score += 1
                # 前后 100 字 snippet
                start = max(0, idx - 100)
                end = min(len(text), idx + len(keyword) + 100)
                snippet = text[start:end].replace("\n", " ").strip()
            if score > 0:
                title = md.stem
                results.append({
                    "path": rel,
                    "title": title,
                    "snippet": snippet[:300],
                    "_score": score,
                })
        results.sort(key=lambda r: -r["_score"])
        return [{k: v for k, v in r.items() if not k.startswith("_")} for r in results[:5]]

    try:
        results = await asyncio.to_thread(_sync_scan)
    except Exception as exc:  # noqa: BLE001
        return {"content": [{"type": "text", "text": f"kb 搜索失败：{exc}"}], "isError": True}

    if not results:
        return {
            "content": [{"type": "text", "text": f'专利知识库未命中"{keyword}"'}],
            "data": [],
        }
    text = (
        f'专利知识库命中 {len(results)} 个文件（按相关度排）:\n'
        + json.dumps(results, ensure_ascii=False, indent=2)
    )
    return {"content": [{"type": "text", "text": text}], "data": results}


async def _do_read_kb_file(*, path: str) -> dict:
    """读 refs/专利专家知识库/<path> 文件内容。"""
    if not path or not path.strip():
        return {"content": [{"type": "text", "text": "path 为空"}], "isError": True}

    def _sync_read() -> dict:
        from pathlib import Path
        kb_root = _get_kb_root()
        rel = path.strip().lstrip("/")
        full = (kb_root / rel).resolve()
        # 防 ../ 越权
        if not str(full).startswith(str(kb_root)):
            return {"ok": False, "msg": "路径越权（escapes kb root）"}
        if not full.exists() or not full.is_file():
            return {"ok": False, "msg": f"文件不存在：{rel}"}
        try:
            text = full.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "msg": f"读取失败：{exc}"}
        return {
            "ok": True,
            "path": rel,
            "size": len(text),
            "content": text[:30000],
            "truncated": len(text) > 30000,
        }

    res = await asyncio.to_thread(_sync_read)
    if not res.get("ok"):
        return {"content": [{"type": "text", "text": res.get("msg", "?")}], "isError": True}
    body = (
        f"kb/{res['path']} ({res['size']} bytes):\n\n{res['content']}"
        + ("\n\n…(已截断到前 30000 字)" if res.get("truncated") else "")
    )
    return {"content": [{"type": "text", "text": body}]}


# ─── file_write_section 业务实现（独立出来便于复用 / 测试） ──────────────────


async def _do_file_write_section(
    *,
    project_id: str,
    name: str,
    content: str,
    parent_folder: str = "AI 输出",
) -> dict:
    """同步 ORM 用 to_thread 包一层，避免阻塞 event loop。"""
    if not project_id:
        return {
            "content": [{"type": "text", "text": "project_id 为空，无法写入"}],
            "isError": True,
        }
    if not name:
        return {
            "content": [{"type": "text", "text": "name 为空，无法写入"}],
            "isError": True,
        }
    # 项目计划.md 是 update_plan 工具的镜像产物，禁止用 file_write_section 直写
    _norm = name.strip().rstrip(".md")
    if _norm in ("项目计划", "工作计划"):
        return {
            "content": [{
                "type": "text",
                "text": "禁止直接写「项目计划.md」—— 请用 update_plan 工具更新计划，后端会自动镜像。",
            }],
            "isError": True,
        }

    def _sync_write() -> dict:
        from .db import SessionLocal
        from .models import FileNode, Project

        db = SessionLocal()
        try:
            proj = db.get(Project, project_id)
            if not proj:
                return {
                    "ok": False,
                    "error": f"project_id={project_id} 不存在",
                }
            # 找 parent_folder
            folder = (
                db.query(FileNode)
                .filter(
                    FileNode.project_id == project_id,
                    FileNode.kind == "folder",
                    FileNode.name == parent_folder,
                )
                .first()
            )
            parent_id: str | None
            if folder is None:
                # fallback：自动建一个 AI 输出 folder（source='ai'）
                parent_id = f"d-{uuid.uuid4().hex[:10]}"
                folder = FileNode(
                    id=parent_id,
                    project_id=project_id,
                    name=parent_folder,
                    kind="folder",
                    parent_id=None,
                    source="ai",
                    hidden=False,
                )
                db.add(folder)
                db.flush()
                created_folder = True
            else:
                parent_id = folder.id
                created_folder = False

            # 文件名补 .md
            fname = name if name.endswith(".md") else f"{name}.md"
            fid = f"f-{uuid.uuid4().hex[:10]}"
            node = FileNode(
                id=fid,
                project_id=project_id,
                name=fname,
                kind="file",
                parent_id=parent_id,
                source="ai",
                mime="text/markdown",
                content=content,
                size=len(content.encode("utf-8")) if content else 0,
                hidden=False,
            )
            db.add(node)
            db.commit()
            return {
                "ok": True,
                "file_id": fid,
                "path": f"{parent_folder}/{fname}",
                "created_folder": created_folder,
            }
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            return {"ok": False, "error": f"写入失败：{exc}"}
        finally:
            db.close()

    result = await asyncio.to_thread(_sync_write)
    if not result.get("ok"):
        return {
            "content": [{"type": "text", "text": result.get("error", "未知错误")}],
            "isError": True,
        }
    text = (
        f"已写入 {result['path']}（file_id={result['file_id']}"
        f"{'，自动创建了文件夹' if result.get('created_folder') else ''}）"
    )
    return {
        "content": [{"type": "text", "text": text}],
        "file_id": result["file_id"],
        "path": result["path"],
    }


# v0.25: 调研下载 — 把重要资料保存到「AI 输出/调研下载/<分类>/」
_RESEARCH_CATEGORY_LABEL = {
    "similar_patent": "类似专利",
    "related_article": "相关文章",
    "note": "调研笔记",
}


async def _do_generate_disclosure(*, project_id: str) -> dict:
    """v0.37 P1: agent 调用此工具直接生成 No34 模板填充的 .docx 落到「AI 输出/专利交底书.docx」。"""
    if not project_id:
        return {"content": [{"type": "text", "text": "project_id 为空"}], "isError": True}

    def _sync_generate() -> dict:
        from datetime import datetime, timezone
        from pathlib import Path
        from .db import SessionLocal
        from .models import FileNode, Project
        from .config import settings as _settings
        from .disclosure_no34 import generate_no34_docx

        db = SessionLocal()
        try:
            p = db.get(Project, project_id)
            if p is None:
                return {"ok": False, "msg": f"project {project_id} not found"}

            blob = generate_no34_docx(project_id, db)

            # 找/建「AI 输出/」根
            ai_root_id = f"root-ai-{project_id}"
            ai_root = db.get(FileNode, ai_root_id)
            if ai_root is None:
                return {"ok": False, "msg": "AI 输出 根目录不存在（项目损坏？）"}

            name = "专利交底书.docx"
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

            # 同名覆盖；保留 file_id 让前端复用引用
            existing = (
                db.query(FileNode)
                .filter(
                    FileNode.project_id == project_id,
                    FileNode.parent_id == ai_root.id,
                    FileNode.name == name,
                )
                .first()
            )
            now = datetime.now(timezone.utc)
            if existing:
                fid = existing.id
            else:
                fid = f"f-{uuid.uuid4().hex[:10]}"

            # 写盘
            storage_dir = Path(_settings.storage_root) / project_id
            storage_dir.mkdir(parents=True, exist_ok=True)
            disk_path = storage_dir / f"{fid}.docx"
            disk_path.write_bytes(blob)

            api_prefix = _settings.api_prefix or "/api"
            url = f"{api_prefix}/projects/{project_id}/files/{fid}/download"

            if existing:
                existing.size = len(blob)
                existing.mime = mime
                existing.url = url
                existing.content = None
                existing.updated_at = now
            else:
                node = FileNode(
                    id=fid,
                    project_id=project_id,
                    name=name,
                    kind="file",
                    parent_id=ai_root.id,
                    source="ai",
                    hidden=False,
                    mime=mime,
                    size=len(blob),
                    url=url,
                    content=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(node)

            # 项目状态推进
            if p.status in ("drafting", "researching"):
                p.status = "completed"

            db.commit()

            return {
                "ok": True,
                "file_id": fid,
                "path": f"AI 输出/{name}",
                "size": len(blob),
            }
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("generate_disclosure failed")
            return {"ok": False, "msg": f"生成失败：{type(exc).__name__}: {exc}"}
        finally:
            db.close()

    res = await asyncio.to_thread(_sync_generate)
    if not res.get("ok"):
        return {"content": [{"type": "text", "text": res.get("msg", "?")}], "isError": True}
    return {
        "content": [{
            "type": "text",
            "text": f"✓ 已生成交底书 → {res['path']} ({res['size']} bytes)。前端文件树会自动出现该文件，点开右栏即可预览/下载。",
        }],
        "file_id": res["file_id"],
        "path": res["path"],
    }


async def _do_save_research(
    *,
    project_id: str,
    name: str,
    content: str,
    category: str = "note",
    source_url: str = "",
) -> dict:
    if not project_id:
        return {"content": [{"type": "text", "text": "project_id 为空"}], "isError": True}
    if not name:
        return {"content": [{"type": "text", "text": "name 为空"}], "isError": True}
    cat_label = _RESEARCH_CATEGORY_LABEL.get(category, "调研笔记")

    def _sync() -> dict:
        from .db import SessionLocal
        from .models import FileNode, Project

        db = SessionLocal()
        try:
            proj = db.get(Project, project_id)
            if not proj:
                return {"ok": False, "error": f"project_id={project_id} 不存在"}

            def _ensure_folder(folder_name: str, parent_id: str | None) -> str:
                """找/建一个 folder 节点，返回其 id。"""
                q = db.query(FileNode).filter(
                    FileNode.project_id == project_id,
                    FileNode.kind == "folder",
                    FileNode.name == folder_name,
                    FileNode.parent_id.is_(None) if parent_id is None else FileNode.parent_id == parent_id,
                )
                existing = q.first()
                if existing:
                    return existing.id
                new_id = f"d-{uuid.uuid4().hex[:10]}"
                db.add(FileNode(
                    id=new_id,
                    project_id=project_id,
                    name=folder_name,
                    kind="folder",
                    parent_id=parent_id,
                    source="ai",
                    hidden=False,
                ))
                db.flush()
                return new_id

            ai_root = _ensure_folder("AI 输出", None)
            research_root = _ensure_folder("调研下载", ai_root)
            cat_folder = _ensure_folder(cat_label, research_root)

            # 写文件，content 头部加 metadata
            fname = name if name.endswith(".md") else f"{name}.md"
            header_lines = [f"# {name}", ""]
            header_lines.append(f"- 分类：{cat_label}")
            if source_url:
                header_lines.append(f"- 来源：{source_url}")
            header_lines.append(f"- 保存时间：{datetime.now(timezone.utc).isoformat()}")
            header_lines.append("")
            header_lines.append("---")
            header_lines.append("")
            full_content = "\n".join(header_lines) + (content or "")

            fid = f"f-{uuid.uuid4().hex[:10]}"
            db.add(FileNode(
                id=fid,
                project_id=project_id,
                name=fname,
                kind="file",
                parent_id=cat_folder,
                source="ai",
                mime="text/markdown",
                content=full_content,
                size=len(full_content.encode("utf-8")),
                url=source_url or None,
                hidden=False,
            ))
            db.commit()
            return {
                "ok": True,
                "file_id": fid,
                "path": f"AI 输出/调研下载/{cat_label}/{fname}",
            }
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            return {"ok": False, "error": f"保存失败：{exc}"}
        finally:
            db.close()

    result = await asyncio.to_thread(_sync)
    if not result.get("ok"):
        return {
            "content": [{"type": "text", "text": result.get("error", "未知错误")}],
            "isError": True,
        }
    return {
        "content": [{
            "type": "text",
            "text": f"已保存到 {result['path']}（file_id={result['file_id']}）",
        }],
        "file_id": result["file_id"],
        "path": result["path"],
    }


# ─── 真实 SDK 路径 ──────────────────────────────────────────────────────────


async def _stream_real_sdk(idea_text: str, max_turns: int) -> AsyncIterator[dict]:
    """走真 SDK；任何异常会被外层 try/except 兜住转 mock。"""
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        AssistantMessage,
        TextBlock,
        ToolUseBlock,
        ResultMessage,
        UserMessage,
    )

    server, allowed = _build_mcp_server()
    # v0.21：用 SystemPromptPreset(exclude_dynamic_sections=True) 让 system 前缀稳定，
    # CLI/底层 API 自动命中 ephemeral cache（前提：CLI 版本支持，旧 CLI 静默忽略）。
    system_prompt_preset = {
        "type": "preset",
        "preset": "claude_code",
        "append": SYSTEM_PROMPT,
        "exclude_dynamic_sections": True,
    }
    options = ClaudeAgentOptions(
        system_prompt=system_prompt_preset,
        mcp_servers={"patent-tools": server},
        allowed_tools=allowed,
        max_turns=max_turns,
    )

    yield {"type": "thinking", "text": "调用 Claude Agent SDK..."}

    async for msg in query(prompt=idea_text, options=options):
        cls = type(msg).__name__
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    yield {"type": "delta", "text": block.text}
                elif isinstance(block, ToolUseBlock):
                    yield {
                        "type": "tool_use",
                        "name": getattr(block, "name", "?"),
                        "input": getattr(block, "input", {}) or {},
                        "id": getattr(block, "id", ""),
                    }
        elif isinstance(msg, UserMessage):
            # tool_result 通常包在 user message 里回灌给 model
            content = getattr(msg, "content", None)
            if isinstance(content, list):
                for blk in content:
                    blk_type = getattr(blk, "type", None) or (blk.get("type") if isinstance(blk, dict) else None)
                    if blk_type == "tool_result":
                        text_parts = []
                        raw = getattr(blk, "content", None) if not isinstance(blk, dict) else blk.get("content")
                        if isinstance(raw, str):
                            text_parts.append(raw)
                        elif isinstance(raw, list):
                            for sub in raw:
                                if isinstance(sub, dict) and sub.get("type") == "text":
                                    text_parts.append(sub.get("text", ""))
                                else:
                                    text_parts.append(str(sub))
                        yield {
                            "type": "tool_result",
                            "text": "\n".join(text_parts),
                        }
        elif isinstance(msg, ResultMessage):
            usage = getattr(msg, "usage", None) or {}
            done_ev = {
                "type": "done",
                "stop_reason": getattr(msg, "stop_reason", None),
                "total_cost_usd": getattr(msg, "total_cost_usd", None),
                "num_turns": getattr(msg, "num_turns", None),
                # v0.21：把 usage 整个 dict 透出，方便前端/日志看 cache hit
                "usage": usage,
                "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
                "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
            }
            yield done_ev
            return
        else:
            logger.debug("agent_sdk: unhandled msg type %s", cls)

    # 如果迭代正常结束但没 ResultMessage：补一个 done
    yield {"type": "done", "stop_reason": "end_of_stream"}


# ─── 对外入口 ───────────────────────────────────────────────────────────────


async def agent_mine_stream(
    idea_text: str,
    *,
    max_turns: int = 8,
    endpoint: str = "mine_spike",
    project_id: str | None = None,
) -> AsyncIterator[dict]:
    """统一入口。SDK 异常 yield error 事件并写 AgentRunLog。"""
    idea_text = (idea_text or "").strip()
    if not idea_text:
        yield {"type": "error", "message": "idea 为空"}
        return

    t0 = time.monotonic()
    last_done: dict | None = None
    last_error: str | None = None

    try:
        try:
            async for ev in _stream_real_sdk(idea_text, max_turns):
                if ev.get("type") == "done":
                    last_done = ev
                elif ev.get("type") == "error":
                    last_error = ev.get("message")
                yield ev
        except Exception as exc:  # noqa: BLE001
            logger.exception("agent_sdk real path failed")
            last_error = f"{type(exc).__name__}: {exc}"
            yield {"type": "error", "message": last_error}
    finally:
        duration_ms = int((time.monotonic() - t0) * 1000)
        try:
            await _write_run_log(
                endpoint=endpoint,
                project_id=project_id,
                idea=idea_text,
                duration_ms=duration_ms,
                done=last_done,
                error=last_error,
            )
        except Exception as exc:  # noqa: BLE001
            # 监控失败绝不阻塞业务
            logger.warning("agent_run_log write failed: %s", exc)


# ─── observability：写 AgentRunLog ───────────────────────────────────────────


async def _write_run_log(
    *,
    endpoint: str,
    project_id: str | None,
    idea: str | None,
    duration_ms: int,
    done: dict | None,
    error: str | None,
) -> None:
    """同步 ORM 用 to_thread 包一层。失败由调用方 try 兜住。"""
    num_turns = None
    total_cost_usd = None
    stop_reason = None
    if isinstance(done, dict):
        num_turns = done.get("num_turns")
        total_cost_usd = done.get("total_cost_usd")
        stop_reason = done.get("stop_reason")

    def _sync_write() -> None:
        from .db import SessionLocal
        from .models import AgentRunLog

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
                fallback_used=False,
                error=(error or None) and str(error)[:2000],
                is_mock=False,
            )
            db.add(row)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    await asyncio.to_thread(_sync_write)
