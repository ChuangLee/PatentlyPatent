"""v0.16 spike-B: Claude Agent SDK 走专利挖掘单端点。

保留 mining.py 老路径不动；本模块独立提供 /api/agent/mine_spike 路由的核心逻辑。

设计：
  - 用 SDK 的 @tool 装饰器把 zhihuiya.query_search_count 包成一个工具
  - in-process MCP server（create_sdk_mcp_server），无子进程开销
  - 没有 ANTHROPIC_API_KEY / use_real_llm=False / SDK 调用失败时，自动 mock 流
  - 把 SDK 的 AssistantMessage / ToolUseBlock / TextBlock / ResultMessage 翻译成统一 dict
  - 对外 yield 的事件类型：thinking / tool_use / tool_result / delta / done / error
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

from .config import settings
from . import zhihuiya

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "你是一名资深专利挖掘助手。用户给出一段技术构思，"
    "你需要：\n"
    "1) 把构思拆成核心技术关键词；\n"
    "2) 调用 search_patents 工具，对若干关键词组合做命中量检索；\n"
    "3) 根据命中量（多=红海，少=可能空白）给出新颖性初步判断；\n"
    "4) 给出 3-5 条可挖掘的差异化角度。\n"
    "保持简洁，工具调用次数不超过 4 次。最后用中文给出结论。"
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

    server = create_sdk_mcp_server(
        name="patent-tools",
        version="0.1.0",
        tools=[search_patents],
    )
    return server, ["mcp__patent-tools__search_patents"]


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
    """没有真 key 时演示完整流程：thinking → tool_use → tool_result → delta×N → done。"""
    yield {"type": "thinking", "text": f"分析构思：{idea_text[:60]}…"}
    await asyncio.sleep(0.05)

    # 简单从输入抽取一个关键词当 demo query
    keyword = "区块链 AND 供应链" if "区块链" in idea_text else (idea_text[:20] or "通用关键词")
    mock_query = f"TAC: ({keyword})"

    yield {
        "type": "tool_use",
        "name": "search_patents",
        "input": {"query": mock_query},
        "id": "mock-tool-1",
    }
    await asyncio.sleep(0.05)

    # 真带智慧芽 token 时也给真数据；没 token 用假数
    try:
        count = await zhihuiya.query_search_count(mock_query) if settings.use_real_zhihuiya else 12345
    except Exception:  # noqa: BLE001
        count = 12345

    yield {"type": "tool_result", "text": f'检索式 "{mock_query}" 命中 {count} 件', "count": count}
    await asyncio.sleep(0.05)

    chunks = [
        f"根据检索结果，相关方向已有 {count} 件公开专利，",
        "属于较为活跃的技术领域。",
        "建议从以下差异化角度切入：\n",
        "1) 共识机制与轻量化签名结合，降低 TPS 瓶颈；\n",
        "2) 跨链验证溯源链的零知识证明压缩；\n",
        "3) 边缘节点与物联网传感器联合上链；\n",
        "（mock 模式输出，未走真 LLM）",
    ]
    for c in chunks:
        yield {"type": "delta", "text": c}
        await asyncio.sleep(0.03)

    yield {"type": "done", "stop_reason": "mock_complete", "mock": True}


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
