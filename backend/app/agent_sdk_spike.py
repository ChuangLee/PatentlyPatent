"""v0.17-A spike: Claude Agent SDK 走专利挖掘单端点（4 工具版）。

保留 mining.py 老路径不动；本模块独立提供 /api/agent/mine_spike 路由的核心逻辑。

设计：
  - 用 SDK 的 @tool 装饰器把 4 个工具包成 in-process MCP server：
      * search_patents      命中量
      * search_trends       年度申请趋势
      * search_applicants   Top 申请人
      * file_write_section  把 markdown 写到 project 文件树
  - in-process MCP server（create_sdk_mcp_server），无子进程开销
  - 没有 ANTHROPIC_API_KEY / use_real_llm=False / SDK 调用失败时，自动 mock 流
  - 把 SDK 的 AssistantMessage / ToolUseBlock / TextBlock / ResultMessage 翻译成统一 dict
  - 对外 yield 的事件类型：thinking / tool_use / tool_result / delta / done / error
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from .config import settings
from . import zhihuiya

logger = logging.getLogger(__name__)


def log_startup_status() -> None:
    """由 main.py 在 lifespan startup 阶段调用一次。

    放在 import 顶层调用会被 logging.basicConfig 之前的 root handler 吞掉，
    所以延迟到 logging 初始化完成后再打。
    """
    logger.info(
        "agent_sdk_spike: use_real_llm=%s has_key=%s use_real_zhihuiya=%s",
        settings.use_real_llm,
        bool(settings.anthropic_api_key),
        settings.use_real_zhihuiya,
    )


SYSTEM_PROMPT = (
    "你是一名资深专利挖掘助手。用户给出一段技术构思，"
    "你需要：\n"
    "1) 把构思拆成核心技术关键词；\n"
    "2) 调用 search_patents / search_trends / search_applicants 工具，对若干"
    "关键词组合做命中量、年度趋势、申请人分布检索；\n"
    "3) 综合判断新颖性、技术热度、主要竞争对手；\n"
    "4) 给出 3-5 条可挖掘的差异化角度；\n"
    "5) 必要时调用 file_write_section 把分析结论写回项目（仅在用户明确要求"
    "保存或调用方传入 project_id 时才写）。\n"
    "保持简洁，工具调用次数不超过 6 次。最后用中文给出结论。"
)


# ─── tool 定义（仅在 SDK 真实调用时使用） ──────────────────────────────────────

def _build_mcp_server():
    """延迟构造，只有在真实 SDK 路径下才需要。

    返回 (server, tool_names) 二元组，便于注册到 ClaudeAgentOptions。
    """
    from claude_agent_sdk import tool, create_sdk_mcp_server

    @tool(
        "search_patents",
        "用智慧芽对一个检索式拿命中量（命中越多越红海）。query 是布尔检索式，例如 'TAC: (区块链 AND 供应链)'。",
        {"query": str},
    )
    async def search_patents(args: dict[str, Any]) -> dict:
        q = (args or {}).get("query", "").strip()
        if not q:
            return {"content": [{"type": "text", "text": "query 为空"}], "isError": True}
        try:
            count = await zhihuiya.query_search_count(q)
        except Exception as exc:  # noqa: BLE001
            logger.warning("search_patents tool failed: %s", exc)
            return {
                "content": [{"type": "text", "text": f"检索失败：{exc}"}],
                "isError": True,
            }
        return {
            "content": [
                {"type": "text", "text": f'检索式 "{q}" 命中 {count} 件'},
            ],
        }

    @tool(
        "search_trends",
        "智慧芽：拿一个检索式近 N 年的专利申请年度趋势。返回各年份的命中量列表（最多 10 年）。lang 默认 cn。",
        {"query": str, "lang": str},
    )
    async def search_trends(args: dict[str, Any]) -> dict:
        q = (args or {}).get("query", "").strip()
        lang = (args or {}).get("lang") or "cn"
        if not q:
            return {"content": [{"type": "text", "text": "query 为空"}], "isError": True}
        try:
            data = await zhihuiya.patent_trends(q, lang=lang)
        except Exception as exc:  # noqa: BLE001
            logger.warning("search_trends tool failed: %s", exc)
            return {
                "content": [{"type": "text", "text": f"趋势查询失败：{exc}"}],
                "isError": True,
            }
        # 截到最近 10 年
        trimmed = data[-10:] if isinstance(data, list) else []
        text = json.dumps(trimmed, ensure_ascii=False)
        return {
            "content": [{"type": "text", "text": text}],
            "data": trimmed,
        }

    @tool(
        "search_applicants",
        "智慧芽：拿一个检索式下的 Top 10 申请人（机构）排名。返回 [{name, count}, ...]。lang 默认 cn。",
        {"query": str, "lang": str},
    )
    async def search_applicants(args: dict[str, Any]) -> dict:
        q = (args or {}).get("query", "").strip()
        lang = (args or {}).get("lang") or "cn"
        if not q:
            return {"content": [{"type": "text", "text": "query 为空"}], "isError": True}
        try:
            raw = await zhihuiya.applicant_ranking(q, lang=lang, n=10)
        except Exception as exc:  # noqa: BLE001
            logger.warning("search_applicants tool failed: %s", exc)
            return {
                "content": [{"type": "text", "text": f"申请人查询失败：{exc}"}],
                "isError": True,
            }
        # 字段归一：智慧芽不同接口字段名不一，尽量兜底
        normalized: list[dict] = []
        for item in (raw or [])[:10]:
            if not isinstance(item, dict):
                continue
            name = (
                item.get("name")
                or item.get("applicant")
                or item.get("applicant_name")
                or item.get("title")
                or ""
            )
            cnt = (
                item.get("count")
                or item.get("num")
                or item.get("amount")
                or item.get("value")
                or 0
            )
            normalized.append({"name": str(name), "count": int(cnt or 0)})
        text = json.dumps(normalized, ensure_ascii=False)
        return {
            "content": [{"type": "text", "text": text}],
            "data": normalized,
        }

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
        return await _do_file_write_section(
            project_id=(args or {}).get("project_id", ""),
            name=(args or {}).get("name", ""),
            content=(args or {}).get("content", ""),
            parent_folder=(args or {}).get("parent_folder") or "AI 输出",
        )

    server = create_sdk_mcp_server(
        name="patent-tools",
        version="0.2.0",
        tools=[search_patents, search_trends, search_applicants, file_write_section],
    )
    allowed = [
        "mcp__patent-tools__search_patents",
        "mcp__patent-tools__search_trends",
        "mcp__patent-tools__search_applicants",
        "mcp__patent-tools__file_write_section",
    ]
    return server, allowed


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
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
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
            yield {
                "type": "done",
                "stop_reason": getattr(msg, "stop_reason", None),
                "total_cost_usd": getattr(msg, "total_cost_usd", None),
                "num_turns": getattr(msg, "num_turns", None),
            }
            return
        else:
            logger.debug("agent_sdk: unhandled msg type %s", cls)

    # 如果迭代正常结束但没 ResultMessage：补一个 done
    yield {"type": "done", "stop_reason": "end_of_stream"}


# ─── Mock 路径 ──────────────────────────────────────────────────────────────


async def _stream_mock(idea_text: str) -> AsyncIterator[dict]:
    """没有真 key 时演示完整流程：thinking → 多个 tool_use/tool_result → delta×N → done。

    v0.17-A：演示 4 个 tool（含新加的 search_trends / search_applicants /
    file_write_section）。file_write_section 走 dry-run，不真写库（mock 模式）。
    """
    yield {"type": "thinking", "text": f"分析构思：{idea_text[:60]}…"}
    await asyncio.sleep(0.05)

    # 简单从输入抽取一个关键词当 demo query
    keyword = "区块链 AND 供应链" if "区块链" in idea_text else (idea_text[:20] or "通用关键词")
    mock_query = f"TAC: ({keyword})"

    # ---- tool 1: search_patents ------------------------------------------
    yield {
        "type": "tool_use",
        "name": "search_patents",
        "input": {"query": mock_query},
        "id": "mock-tool-1",
    }
    await asyncio.sleep(0.03)
    try:
        count = await zhihuiya.query_search_count(mock_query) if settings.use_real_zhihuiya else 12345
    except Exception:  # noqa: BLE001
        count = 12345
    yield {"type": "tool_result", "text": f'检索式 "{mock_query}" 命中 {count} 件', "count": count}
    await asyncio.sleep(0.03)

    # ---- tool 2: search_trends -------------------------------------------
    yield {
        "type": "tool_use",
        "name": "search_trends",
        "input": {"query": mock_query, "lang": "cn"},
        "id": "mock-tool-2",
    }
    await asyncio.sleep(0.03)
    try:
        trends = (
            await zhihuiya.patent_trends(mock_query, lang="cn")
            if settings.use_real_zhihuiya
            else [
                {"year": 2017, "count": 120}, {"year": 2018, "count": 240},
                {"year": 2019, "count": 410}, {"year": 2020, "count": 720},
                {"year": 2021, "count": 980}, {"year": 2022, "count": 1100},
                {"year": 2023, "count": 1320}, {"year": 2024, "count": 1280},
                {"year": 2025, "count": 1190},
            ]
        )
    except Exception:  # noqa: BLE001
        trends = []
    trends = (trends or [])[-10:]
    yield {
        "type": "tool_result",
        "text": json.dumps(trends, ensure_ascii=False),
        "data": trends,
    }
    await asyncio.sleep(0.03)

    # ---- tool 3: search_applicants ---------------------------------------
    yield {
        "type": "tool_use",
        "name": "search_applicants",
        "input": {"query": mock_query, "lang": "cn"},
        "id": "mock-tool-3",
    }
    await asyncio.sleep(0.03)
    if settings.use_real_zhihuiya:
        try:
            raw = await zhihuiya.applicant_ranking(mock_query, lang="cn", n=10)
        except Exception:  # noqa: BLE001
            raw = []
        applicants = []
        for item in (raw or [])[:10]:
            if isinstance(item, dict):
                applicants.append({
                    "name": str(item.get("name") or item.get("applicant") or ""),
                    "count": int(item.get("count") or item.get("num") or 0),
                })
    else:
        applicants = [
            {"name": "腾讯", "count": 320},
            {"name": "阿里巴巴", "count": 285},
            {"name": "蚂蚁集团", "count": 210},
            {"name": "百度", "count": 180},
            {"name": "京东", "count": 142},
        ]
    yield {
        "type": "tool_result",
        "text": json.dumps(applicants, ensure_ascii=False),
        "data": applicants,
    }
    await asyncio.sleep(0.03)

    # ---- tool 4: file_write_section（mock 不真写） ------------------------
    yield {
        "type": "tool_use",
        "name": "file_write_section",
        "input": {
            "project_id": "(mock)",
            "name": "agent 分析摘要",
            "content": "（演示：mock 模式不写库）",
            "parent_folder": "AI 输出",
        },
        "id": "mock-tool-4",
    }
    await asyncio.sleep(0.03)
    yield {
        "type": "tool_result",
        "text": "mock 模式：未真实写入。真实模式下会创建 AI 输出/agent 分析摘要.md",
    }
    await asyncio.sleep(0.03)

    # ---- 最终 deltas ------------------------------------------------------
    chunks = [
        f"根据检索结果，相关方向已有 {count} 件公开专利，",
        f"近 10 年趋势数据点 {len(trends)} 条，",
        f"Top 申请人 {len(applicants)} 家，",
        "属于较为活跃的技术领域。",
        "建议从以下差异化角度切入：\n",
        "1) 共识机制与轻量化签名结合，降低 TPS 瓶颈；\n",
        "2) 跨链验证溯源链的零知识证明压缩；\n",
        "3) 边缘节点与物联网传感器联合上链；\n",
        "（mock 模式输出，未走真 LLM）",
    ]
    for c in chunks:
        yield {"type": "delta", "text": c}
        await asyncio.sleep(0.02)

    yield {
        "type": "done",
        "stop_reason": "mock_complete",
        "mock": True,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# ─── 对外入口 ───────────────────────────────────────────────────────────────


async def agent_mine_stream(
    idea_text: str,
    *,
    max_turns: int = 8,
) -> AsyncIterator[dict]:
    """统一入口。无 key 或 SDK 异常时走 mock。"""
    idea_text = (idea_text or "").strip()
    if not idea_text:
        yield {"type": "error", "message": "idea 为空"}
        return

    if not settings.use_real_llm:
        async for ev in _stream_mock(idea_text):
            yield ev
        return

    # 真 SDK 路径，外层兜底
    try:
        async for ev in _stream_real_sdk(idea_text, max_turns):
            yield ev
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent_sdk real path failed, falling back to mock")
        yield {"type": "error", "message": f"SDK 调用失败，降级 mock：{exc}"}
        async for ev in _stream_mock(idea_text):
            yield ev
