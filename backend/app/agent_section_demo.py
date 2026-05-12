"""v0.17-C: 用 agent SDK 跑同一个章节生成的 demo（与 mining.py 老路径并行）。

- 选定章节: "01-背景技术"（prior_art），mining.py 中由 build_sections() 第 1 个元素生成
- mining.py 老路径: 一次性输出 markdown 模板 + [LLM_INJECT::xxx] 占位，后续靠 chat.py 流式回填
- agent 版: 让 LLM 自主决定调用 search_patents / patent_trends / applicant_ranking 等工具，
            最终输出该章节的完整 markdown（无占位）

不修改 mining.py。无 key 时走 mock 流（结构与真实 SDK 一致）。
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator

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
        "  - 调研中遇到与本案高度相关的具体专利文献，调用 save_research(category='similar_patent') 把要点摘要存到「AI 输出/调研下载/类似专利/」便于后续查阅\n"
        "  - 工具调用总次数 ≤ 5\n"
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
    "embodiments": (
        "你是专利交底书的【具体实施例】章节生成器。\n"
        "目标：基于用户的 idea_text（以及可选的项目内已上传资料），产出至少 2 个完整的实施例。\n"
        "每个实施例必须包含：\n"
        "  - 实施原理（为什么这样能 work，1-2 段）\n"
        "  - 关键步骤（编号列表，每步可独立成为方法权要的一个 step）\n"
        "  - 关键参数 / 阈值（端点 + 优选值；A26.3 充分公开必备）\n"
        "工具使用要求：\n"
        "  - 可选调用 file_search_in_project 找用户已上传的实现资料 / 代码片段（若工具可用）\n"
        "  - 可选调用 search_patents 看相邻技术域，避免与现有方案太近\n"
        "  - 工具调用总次数 ≤ 4\n"
        "硬约束：\n"
        "  - 严禁瞎编实验数据 / 性能数字（没有就明确写「需补充」）\n"
        "  - 输出纯 markdown，末尾不写 Examiner 自检（外层模板会拼接）\n"
    ),
    "claims": (
        "你是【独立权要概括度评估器】，专注 CN 实务的三档独权草拟。\n"
        "目标：基于 idea_text，输出 broad / medium / narrow 三档独权草拟，每档：\n"
        "  - 独权 1 条（5-9 项技术特征，逐条编号；动词开头；含必要技术特征最小集 R20.2）\n"
        "  - 概括度说明（上位词激进度 / 中位 / 下位紧贴实施例）\n"
        "  - 风险点（潜在 X 全 / Y 缺新颖性 / 公开不充分 等，1-2 条）\n"
        "工具使用要求：\n"
        "  - 可选调用 search_patents 看相邻技术域命中量，估计 broad 档是否落入红海\n"
        "  - 工具调用总次数 ≤ 3\n"
        "硬约束：\n"
        "  - 三档独权之间应是同一技术构思的不同概括层级，不能跑题\n"
        "  - 输出纯 markdown，末尾不写 Examiner 自检（外层模板会拼接）\n"
    ),
    "drawings_description": (
        "你是【附图说明】章节生成器。\n"
        "目标：基于 idea_text 列出 3-5 张关键附图标题 + 简要说明，\n"
        "覆盖以下任意类别（按需挑选）：数据流 / 系统架构 / 时序 / 状态 / 部署。\n"
        "工具使用要求：\n"
        "  - 可选调用 file_search_in_project 看用户已上传的架构资料/设计图，\n"
        "    若命中则参考其中真实模块名命名图\n"
        "  - 工具调用总次数 ≤ 2\n"
        "硬约束：\n"
        "  - 不要瞎编不存在的图（如用户没上传，给「建议补充」提示）\n"
        "  - 每张图：图号 + 标题 + 一句话说明（≤40 字）\n"
        "  - 输出纯 markdown，末尾不写 Examiner 自检\n"
    ),
    "summary": (
        "你是【发明内容/概述】章节生成器。\n"
        "目标：用 3 段话讲清楚——技术问题 → 核心方案 → 关键效果。\n"
        "格式硬约束：\n"
        "  - 三段，每段 ≤80 字\n"
        "  - 段落 1：技术问题（针对什么 baseline 的什么缺陷）\n"
        "  - 段落 2：核心方案（≥1 个动词开头的手段，含 1-2 个关键模块名）\n"
        "  - 段落 3：关键效果（量化数字优先于形容词）\n"
        "工具使用要求：\n"
        "  - 可选调用 search_patents 验证关键词热度，但不必（≤1 次）\n"
        "硬约束：\n"
        "  - 不堆砌专利套话；不写 Examiner 自检（外层模板会拼接）\n"
        "  - 输出纯 markdown\n"
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
        ResultMessage,
        StreamEvent,
        ToolUseBlock,
        UserMessage,
    )

    sys_prompt = _SECTION_PROMPTS.get(section, _SECTION_PROMPTS["prior_art"])
    server, allowed = _build_mcp_server()
    options = ClaudeAgentOptions(
        system_prompt=sys_prompt,
        mcp_servers={"patent-section-tools": server},
        allowed_tools=allowed,
        max_turns=max_turns,
        include_partial_messages=True,   # v0.36.3: token 级流
    )

    yield {"type": "thinking", "text": f"agent 启动: section={section}"}
    seen_tool_use_ids: set[str] = set()

    async for msg in query(prompt=idea_text, options=options):
        if isinstance(msg, StreamEvent):
            ev = msg.event or {}
            if ev.get("type") == "content_block_delta":
                delta = ev.get("delta") or {}
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        yield {"type": "delta", "text": text}
            elif ev.get("type") == "content_block_start":
                cb = ev.get("content_block") or {}
                if cb.get("type") == "thinking":
                    yield {"type": "thinking", "text": "🤔 正在推理…"}
            # 其它 SDK 内部事件不透传
        elif isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, ToolUseBlock):
                    bid = getattr(block, "id", "") or f"auto-{len(seen_tool_use_ids)}"
                    if bid in seen_tool_use_ids:
                        continue
                    seen_tool_use_ids.add(bid)
                    yield {
                        "type": "tool_use",
                        "name": getattr(block, "name", "?"),
                        "input": getattr(block, "input", {}) or {},
                        "id": bid,
                    }
        elif isinstance(msg, UserMessage):
            content = getattr(msg, "content", None)
            if isinstance(content, list):
                for blk in content:
                    # v0.36.4: partial 模式 ToolResultBlock 兼容
                    is_tool_result = (
                        type(blk).__name__ == "ToolResultBlock"
                        or hasattr(blk, "tool_use_id")
                        or (isinstance(blk, dict) and blk.get("type") == "tool_result")
                    )
                    if not is_tool_result:
                        continue
                    raw = (
                        getattr(blk, "content", None)
                        if not isinstance(blk, dict)
                        else blk.get("content")
                    )
                    is_err = bool(getattr(blk, "is_error", False)) if not isinstance(blk, dict) else bool(blk.get("is_error"))
                    tool_use_id = (
                        getattr(blk, "tool_use_id", None) if not isinstance(blk, dict)
                        else blk.get("tool_use_id")
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
                    ev = {"type": "tool_result", "text": text}
                    if tool_use_id:
                        ev["tool_use_id"] = tool_use_id
                    if is_err:
                        ev["is_error"] = True
                    yield ev
        elif isinstance(msg, ResultMessage):
            yield {
                "type": "done",
                "stop_reason": getattr(msg, "stop_reason", None),
                "total_cost_usd": getattr(msg, "total_cost_usd", None),
                "num_turns": getattr(msg, "num_turns", None),
            }
            return

    yield {"type": "done", "stop_reason": "end_of_stream"}


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

    try:
        async for ev in _stream_real_sdk(section, idea_text, max_turns):
            yield ev
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent_section real path failed")
        yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
