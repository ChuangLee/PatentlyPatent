# v0.16 spike-B：Claude Agent SDK 接入后端

## 目标
在不动 `mining.py` / `llm.py` / 老 chat 路由的前提下，用 Claude Agent SDK 跑通一个**专利挖掘单端点 demo**，验证：
- SDK 能不能装、API 形态长啥样
- 能不能把 `zhihuiya.query_search_count` 包成一个 SDK tool
- SSE 流能不能转出 `thinking / tool_use / tool_result / delta / done` 5 类事件
- 没有 `ANTHROPIC_API_KEY` 时能不能走 mock 模式继续 demo

## 装的包
```
claude-agent-sdk == 0.1.77   # PyPI
依赖：mcp-1.27.0, jsonschema, httpx-sse, cryptography 等
Python 要求：>=3.10
认证：依赖 bundled Claude Code CLI；或 ANTHROPIC_API_KEY 环境变量
```

## API 形态（30 行示例）
```python
from claude_agent_sdk import (
    query, ClaudeAgentOptions, tool, create_sdk_mcp_server,
    AssistantMessage, TextBlock, ToolUseBlock, ResultMessage,
)

@tool("search_patents", "智慧芽命中量检索", {"query": str})
async def search_patents(args):
    count = await zhihuiya.query_search_count(args["query"])
    return {"content": [{"type": "text", "text": f"命中 {count} 件"}]}

server = create_sdk_mcp_server(
    name="patent-tools", version="0.1.0", tools=[search_patents],
)

options = ClaudeAgentOptions(
    system_prompt="你是专利挖掘助手...",
    mcp_servers={"patent-tools": server},
    allowed_tools=["mcp__patent-tools__search_patents"],
    max_turns=8,
)

async for msg in query(prompt="基于区块链的供应链溯源", options=options):
    if isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):   yield {"type": "delta", "text": block.text}
            elif isinstance(block, ToolUseBlock): yield {"type": "tool_use", "name": block.name, "input": block.input}
    elif isinstance(msg, ResultMessage):
        yield {"type": "done", "stop_reason": msg.stop_reason}
```

## tool 注册方式
- 用 `@tool(name, description, input_schema)` 装饰一个 `async def fn(args: dict)`
- 返回 `{"content":[{"type":"text","text":"..."}]}`，错误加 `"isError": True`
- 把多个 tool 喂给 `create_sdk_mcp_server(name, version, tools=[...])`，得到一个 in-process MCP server（**无子进程开销**，跟手工 stdio MCP server 不一样）
- 把 server 传给 `ClaudeAgentOptions(mcp_servers={...}, allowed_tools=["mcp__<server-name>__<tool-name>"])` —— 注意 allowed_tools 字符串前缀 `mcp__patent-tools__search_patents` 是 SDK 约定，少了就触发权限确认

## 与现有 `mining.py` 直调 Anthropic SDK 的对比

| 维度 | mining.py（旧） | agent_sdk_spike.py（新） |
|---|---|---|
| 客户端 | `anthropic.AsyncAnthropic` 原生 | `claude_agent_sdk.query()` |
| 工具调用 | 手工 round-trip：判 `stop_reason==tool_use` → 调函数 → 拼回 `tool_result` 进下一轮 | SDK 自动循环；agent 自己决定调几次 |
| 多轮控制 | 手写 while 循环 | `max_turns` 参数 |
| 流式 | 手工解析 `delta`/`message_stop` | 高层 message 对象（`AssistantMessage` / `ResultMessage` 等） |
| 工具定义 | dict schema + Python 回调字典 | `@tool` 装饰器 + `create_sdk_mcp_server`（in-proc MCP） |
| Prompt cache | 手工加 `cache_control` | SDK 自动管理（按官方 docs） |
| 子代理 / 钩子 | 无 | `hooks=` / 子代理体系 |
| 灵活度 | 高（每个 byte 自己控） | 中（贴 SDK 抽象走） |
| 代码量 | mining.py 一大坨 | spike 模块 ~150 行 |

**结论**：Agent SDK 的卖点是把 "工具循环 + 多轮 + 权限 + cache" 收成一个 `query()`，适合做成熟的挖掘 agent；但定制化（比如自己埋打点、自己控 token cost、自己拼 prompt cache 块）不如 mining.py 直调灵活。建议两条路并存：

- 复杂可控流程 → 老 mining.py 直调
- 探索式 agent 流程（多工具 / 多轮 / 自决策）→ 新 spike 模块

## 验证结果

```bash
curl -sN -X POST https://blind.pub/patent/api/agent/mine_spike \
  -H "Content-Type: application/json" \
  -d '{"idea":"基于区块链的供应链溯源新方案"}'
```

Mock 模式（当前生产 use_real_llm=false）下成功输出 11 个 SSE 事件：
1. `thinking` — 解析构思
2. `tool_use` — 调 search_patents("TAC: (区块链 AND 供应链)")
3. `tool_result` — 命中 **2458 件**（真智慧芽返回）
4–10. `delta × 7` — 渐进文本输出
11. `done` — `stop_reason=mock_complete`

## 已知问题 / TODO

1. **没有 ANTHROPIC_API_KEY**：当前服务器 `use_real_llm=false`，验证只走 mock。真 SDK 路径已写好兜底（`_stream_real_sdk` + try/except 降级 mock），但**没在真环境跑过**——key 配上后需补一次端到端测试。
2. **只接了 1 个 tool**：还需要把 `patent_trends` / `applicant_ranking` / `inventor_ranking` / `legal_status` 也包成 SDK tool，让 agent 自决策组合。
3. **max_turns 调优**：当前默认 8 是拍脑袋；要看真实 trace 里 agent 平均 round-trip 数。
4. **Prompt cache**：SDK 文档说自动管理，但没验证实际 cache hit rate。需要拉日志确认。
5. **流量切分**：目前 `/agent/mine_spike` 是新端点；后续要不要把老 `/projects/:id/auto-mining` 切到这条 SDK 路径，需要决策（影响向后兼容）。
6. **错误事件 schema**：`error` 事件目前是 `{type, message}`，前端怎么展示还没设计。
7. **SDK 子进程模式**：claude-agent-sdk 默认通过 Claude Code CLI 子进程跑。生产部署时需要确认 systemd 容器里能找到 `claude` 二进制，或显式配置 SDK 走纯 API 模式。

## 修改/新增文件清单
- 新增 `backend/app/agent_sdk_spike.py`（核心模块，~150 行，mock + 真 SDK 双路径）
- 新增 `backend/app/routes/agent.py`（SSE 路由 `POST /api/agent/mine_spike`）
- 修改 `backend/app/main.py`（+2 行：import + include_router）
- 修改 `backend/.venv` 装包（+claude-agent-sdk 0.1.77 及其依赖）
- 新增 `docs/agent_sdk_spike.md`（本文）
- **未改动**：`mining.py` / `llm.py` / `routes/chat.py` / 前端任何文件
