"""v0.17-C: 用 agent SDK 跑同一个章节生成的 demo（与 mining.py 老路径并行）。

- 选定章节: "01-背景技术"（prior_art），mining.py 中由 build_sections() 第 1 个元素生成
- mining.py 老路径: 一次性输出 markdown 模板 + [LLM_INJECT::xxx] 占位，后续靠 chat.py 流式回填
- agent 版: 让 LLM 自主决定调用 search_patents / patent_trends / applicant_ranking 等工具，
            最终输出该章节的完整 markdown（无占位）

不修改 mining.py。无 key 时走 mock 流（结构与真实 SDK 一致）。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

from .config import settings
from . import zhihuiya

logger = logging.getLogger(__name__)


# ─── 章节级聚焦 system prompt（每个 section 一个）─────────────────────────────

_SECTION_PROMPTS: dict[str, str] = {
    "prior_art": (
        "你是一名资深专利代理人，正在为一份交底书写【一、背景技术】这一节。\n"
        "目标：基于用户的技术构思（idea_text），产出一份完整的 markdown，包含：\n"
        "  1.1 技术领域定位（领域 / 细分赛道 / 3 个典型应用场景）\n"
        "  1.2 报门描述原文回扣\n"
        "  1.3 与本案最相近的现有技术（3-5 篇候选）\n"
        "  1.4 现有技术演进脉络（≤120 字）\n"
        "工具使用要求：\n"
        "  - 必须调用 search_patents 至少 1 次，估算赛道热度（命中量 = 红海/蓝海信号）\n"
        "  - 可选调用 patent_trends 看年度趋势、applicant_ranking 看 top 申请人\n"
        "  - 工具调用总次数 ≤ 4\n"
        "输出风格：\n"
        "  - 客观铺陈，不贬损现有技术\n"
        "  - 数字优先于形容词\n"
        "  - 末尾不要写 Examiner 自检（外层模板会拼接）\n"
    ),
    "applicant_trend": (
        "你是一名专利情报分析师，正在生成【申请人趋势】小节。\n"
        "调用 applicant_ranking + patent_trends 拿真实数据，"
        "输出 markdown 表格 + 1 段趋势点评（≤200 字）。\n"
        "工具调用 ≤ 3 次。"
    ),
}


# ─── tool 定义：比 spike 多两个（trends / applicants），让 LLM 有自由组合空间 ──

def _build_mcp_server():
    """延迟构造，仅真实 SDK 路径用。返回 (server, allowed_tool_names)"""
    from claude_agent_sdk import tool, create_sdk_mcp_server

    @tool(
        "search_patents",
        "对一个布尔检索式拿命中量（命中越多越红海）。query 例如 'TAC: (区块链 AND 供应链)'。",
        {"query": str},
    )
    async def search_patents(args: dict[str, Any]) -> dict:
        q = (args or {}).get("query", "").strip()
        if not q:
            return {"content": [{"type": "text", "text": "query 为空"}], "isError": True}
        try:
            count = await zhihuiya.query_search_count(q)
        except Exception as exc:  # noqa: BLE001
            return {"content": [{"type": "text", "text": f"检索失败：{exc}"}], "isError": True}
        return {"content": [{"type": "text", "text": f'检索式 "{q}" 命中 {count} 件'}]}

    @tool(
        "patent_trends",
        "拿专利申请的年度趋势数据；返回 [{year, count}, ...]。",
        {"query": str},
    )
    async def patent_trends_tool(args: dict[str, Any]) -> dict:
        q = (args or {}).get("query", "").strip()
        try:
            data = await zhihuiya.patent_trends(q)
        except Exception as exc:  # noqa: BLE001
            return {"content": [{"type": "text", "text": f"趋势查询失败：{exc}"}], "isError": True}
        return {"content": [{"type": "text", "text": f"趋势：{data}"}]}

    @tool(
        "applicant_ranking",
        "拿 top N 申请人排名。",
        {"query": str, "n": int},
    )
    async def applicant_ranking_tool(args: dict[str, Any]) -> dict:
        q = (args or {}).get("query", "").strip()
        n = int((args or {}).get("n", 10))
        try:
            data = await zhihuiya.applicant_ranking(q, n=n)
        except Exception as exc:  # noqa: BLE001
            return {"content": [{"type": "text", "text": f"申请人查询失败：{exc}"}], "isError": True}
        return {"content": [{"type": "text", "text": f"top 申请人：{data}"}]}

    server = create_sdk_mcp_server(
        name="patent-section-tools",
        version="0.1.0",
        tools=[search_patents, patent_trends_tool, applicant_ranking_tool],
    )
    allowed = [
        "mcp__patent-section-tools__search_patents",
        "mcp__patent-section-tools__patent_trends",
        "mcp__patent-section-tools__applicant_ranking",
    ]
    return server, allowed


# ─── 真实 SDK 路径 ──────────────────────────────────────────────────────────

async def _stream_real_sdk(
    section: str,
    idea_text: str,
    max_turns: int,
) -> AsyncIterator[dict]:
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        AssistantMessage,
        TextBlock,
        ToolUseBlock,
        ResultMessage,
        UserMessage,
    )

    sys_prompt = _SECTION_PROMPTS.get(section, _SECTION_PROMPTS["prior_art"])
    server, allowed = _build_mcp_server()
    options = ClaudeAgentOptions(
        system_prompt=sys_prompt,
        mcp_servers={"patent-section-tools": server},
        allowed_tools=allowed,
        max_turns=max_turns,
    )

    yield {"type": "thinking", "text": f"agent 启动: section={section}"}

    async for msg in query(prompt=idea_text, options=options):
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
            content = getattr(msg, "content", None)
            if isinstance(content, list):
                for blk in content:
                    blk_type = getattr(blk, "type", None) or (
                        blk.get("type") if isinstance(blk, dict) else None
                    )
                    if blk_type == "tool_result":
                        raw = (
                            getattr(blk, "content", None)
                            if not isinstance(blk, dict)
                            else blk.get("content")
                        )
                        text = ""
                        if isinstance(raw, str):
                            text = raw
                        elif isinstance(raw, list):
                            parts = []
                            for sub in raw:
                                if isinstance(sub, dict) and sub.get("type") == "text":
                                    parts.append(sub.get("text", ""))
                                else:
                                    parts.append(str(sub))
                            text = "\n".join(parts)
                        yield {"type": "tool_result", "text": text}
        elif isinstance(msg, ResultMessage):
            yield {
                "type": "done",
                "stop_reason": getattr(msg, "stop_reason", None),
                "total_cost_usd": getattr(msg, "total_cost_usd", None),
                "num_turns": getattr(msg, "num_turns", None),
            }
            return

    yield {"type": "done", "stop_reason": "end_of_stream"}


# ─── Mock 路径（核心：演示 LLM 自驱多 tool 调用的事件流形态）──────────────────

async def _stream_mock_prior_art(
    idea_text: str, context: dict
) -> AsyncIterator[dict]:
    """模拟 agent 自主调 2 个 tool 后产出完整背景技术 markdown。"""
    title = context.get("title") or "未命名项目"
    domain = context.get("domain") or "通用"

    yield {"type": "thinking", "text": f"准备为「{title}」生成背景技术，先抽关键词…"}
    await asyncio.sleep(0.03)

    keyword = "区块链 AND 供应链" if "区块链" in idea_text else (idea_text[:20] or "通用方向")
    q1 = f"TAC: ({keyword})"

    # —— 第 1 次工具：search_patents
    yield {
        "type": "tool_use",
        "name": "search_patents",
        "input": {"query": q1},
        "id": "mock-1",
    }
    await asyncio.sleep(0.03)
    try:
        c1 = (
            await zhihuiya.query_search_count(q1)
            if settings.use_real_zhihuiya
            else 8421
        )
    except Exception:  # noqa: BLE001
        c1 = 8421
    yield {"type": "tool_result", "text": f'检索式 "{q1}" 命中 {c1} 件'}
    await asyncio.sleep(0.03)

    # —— 第 2 次工具：applicant_ranking（agent 看到红海后决定补查 top 申请人）
    yield {
        "type": "tool_use",
        "name": "applicant_ranking",
        "input": {"query": q1, "n": 5},
        "id": "mock-2",
    }
    await asyncio.sleep(0.03)
    yield {
        "type": "tool_result",
        "text": (
            "top 申请人：[{'name':'IBM','count':312},"
            "{'name':'阿里巴巴','count':278},"
            "{'name':'腾讯','count':201}]"
        ),
    }
    await asyncio.sleep(0.03)

    # —— LLM 综合产出最终 markdown
    final_md = f"""# 一、背景技术

## 1.1 技术领域定位
- **本案领域**：{domain}
- **细分赛道**：{title}（基于用户描述判定）
- **典型应用场景**：
  - 跨企业供应链溯源
  - 食品/药品冷链合规
  - 跨境贸易单据存证

## 1.2 报门描述原文
> {(idea_text or '（未填写）').strip()}

## 1.3 最相近的现有技术（基于智慧芽实时检索）
- 检索式 `{q1}` 命中 **{c1}** 件，赛道处于活跃期。
- 头部申请人：IBM（312 件）、阿里巴巴（278 件）、腾讯（201 件）。
- 候选对照专利由命中集排序后人工筛选 3-5 篇填入下表：

| # | 标题 / 出处 | 公开年 | 核心手段 | 与本案差距 |
|---|---|---|---|---|
| A | （由代理人在命中集中筛选） | — | — | — |
| B | — | — | — | — |
| C | — | — | — | — |

## 1.4 演进脉络
早期方案多依赖中心化数据库做溯源；主流方案转向联盟链 + 智能合约；当前 SOTA
向跨链零知识压缩演进。本案在【SOTA 之后/之外】进一步优化吞吐与隐私。

（mock 模式：两次工具调用被串成一段决策链；真实 SDK 下 LLM 会根据中间结果改写检索式）
"""

    # 切片成 delta 流，模拟流式出文
    for i in range(0, len(final_md), 80):
        yield {"type": "delta", "text": final_md[i : i + 80]}
        await asyncio.sleep(0.02)

    yield {
        "type": "done",
        "stop_reason": "mock_complete",
        "mock": True,
        "tool_calls": 2,
    }


# ─── 对外入口 ───────────────────────────────────────────────────────────────

async def mine_section_via_agent(
    section: str,
    context: dict,
    *,
    max_turns: int = 8,
) -> AsyncIterator[dict]:
    """yields events: thinking / tool_use / tool_result / delta / done / error

    section: 章节 tag（如 'prior_art' / 'applicant_trend'）
    context: {idea_text, title, domain, project_id, ...}
    """
    idea_text = (context.get("idea_text") or context.get("description") or "").strip()
    if not idea_text:
        yield {"type": "error", "message": "idea_text 为空"}
        return

    if section not in _SECTION_PROMPTS:
        yield {
            "type": "error",
            "message": f"未知 section={section}（已知：{list(_SECTION_PROMPTS)}）",
        }
        return

    if not settings.use_real_llm:
        # 目前 mock 仅实现 prior_art，其余 section 直接复用同一份（演示用）
        async for ev in _stream_mock_prior_art(idea_text, context):
            yield ev
        return

    try:
        async for ev in _stream_real_sdk(section, idea_text, max_turns):
            yield ev
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent_section real path failed")
        yield {"type": "error", "message": f"SDK 失败，降级 mock：{exc}"}
        async for ev in _stream_mock_prior_art(idea_text, context):
            yield ev
