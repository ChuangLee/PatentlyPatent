# claude-agent-sdk Prompt Cache 调研（v0.20）

## 1. SDK 版本

- 包名：`claude-agent-sdk`，version **0.1.77**（位于 `backend/.venv`）
- 底层依赖 Claude Code CLI 走 OAuth；SDK 本身是 CLI 的 Python 封装
- 调研日期：2026-05-08

## 2. system_prompt 类型签名

`ClaudeAgentOptions.system_prompt`（types.py:1604）：

```python
system_prompt: str | SystemPromptPreset | SystemPromptFile | None = None
```

- `str` — 直接传字符串
- `SystemPromptPreset` — `{type:"preset", preset:"claude_code", append?:str, exclude_dynamic_sections?:bool}`
- `SystemPromptFile` — `{type:"file", path:str}`

**关键发现**：SDK 当前**不接受** `list[ContentBlock]` / 不暴露 `cache_control` 字段；
也无法手工把 `{type:"text",text:..., cache_control:{type:"ephemeral"}}` 直接传给 system_prompt。

`grep cache_control` 在整个 SDK 包内 0 命中。

## 3. SDK 内的"缓存友好"杠杆

types.py:35-52 的 `SystemPromptPreset.exclude_dynamic_sections`（NotRequired bool）：

> Strip per-user dynamic sections (working directory, auto-memory, git status)
> from the system prompt so it stays static and cacheable across users.

这是 SDK 当前**唯一显式的 prompt cache 优化点**：用 preset 模式 + `exclude_dynamic_sections=True` 让 system 前缀稳定，CLI/底层 API 自动命中 ephemeral cache。
（旧 CLI 会静默忽略此选项，需要新 CLI。）

## 4. ResultMessage 是否暴露 cache token 数据

types.py:1144 `ResultMessage` 含 `usage: dict[str, Any] | None` 和 `model_usage: dict[str, Any] | None` — 是 dict 透传，
**理论上**底层 API 返回的 `cache_creation_input_tokens` / `cache_read_input_tokens` 会落在这里，但 SDK 不做强类型暴露。

## 5. 实测尝试

未实测：当前 `settings.use_real_llm=False`（ping 返回 `use_real_llm:false`），跑的都是 mock 路径，无法触发真 SDK；
且本机 claude CLI OAuth 状态未确认。**实测推迟到 use_real_llm=True 切换后**。

## 6. 推荐：是否启用 + 怎么开

**结论：能开但工程价值有限，不阻塞 v0.20**。

- ✅ 第一步（零成本）：`agent_sdk_spike._build_options()` 把 `system_prompt=str` 改为
  `{"type":"preset","preset":"claude_code","append":<我们的 system>, "exclude_dynamic_sections": True}`。
  对多用户共享前缀的场景（同一份 _SECTION_PROMPTS 被所有项目共用）能跨用户命中 cache。
- ❌ 第二步（不可行）：把 system 改成 list[ContentBlock] 并加 `cache_control` —— 0.1.77 SDK 不支持。
  如要走这条路必须直接调 anthropic SDK，绕过 claude-agent-sdk。
- 📝 监控：把 ResultMessage.usage 整个 dict 写进 AgentRunLog（新加 column 或塞 error 字段尾部），上线后看 cache_read_input_tokens / cache_creation_input_tokens 比值。

**当前不在 v0.20 范围内启用**：mock 路径无 cache 概念；real SDK 路径还没跑通端到端，
等真 LLM 切换后再做 step 1（preset + exclude_dynamic_sections）+ step 3（usage 落库）。

## 参考

- SDK 源：`backend/.venv/lib/python3.12/site-packages/claude_agent_sdk/types.py`
- 入口构造：`backend/app/agent_sdk_spike.py::_build_options`
