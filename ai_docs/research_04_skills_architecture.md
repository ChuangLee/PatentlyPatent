# 调研 4：Claude Skills 架构最佳实践

## 1. SKILL.md 规范与目录约定

**Frontmatter**：
```yaml
---
name: skill-id                       # 必需：小写+连字符
description: 动词+触发场景...         # 推荐：≤150字（首句含 3 个关键动词）
when_to_use: 额外触发条件             # 可选
disable-model-invocation: false      # 可选：仅手动 /xxx
allowed-tools: Bash(git *) Read      # 可选：预授权工具
context: fork                        # 可选：隔离子 agent
paths: "*.patent,*.application.md"   # 可选：路径过滤
---
```

**标准目录**（参考 anthropics/skills）：
```
patent-research/                  # 主控
├── SKILL.md                      # ≤500 行
├── references/                   # 长期知识（不阻塞 context）
├── scripts/                      # 工具脚本/router
└── templates/                    # 模板
```

## 2. 主控调度子 Skill 的 3 种模式

1. **文档式 Router**（⭐⭐⭐）— 主 SKILL.md 写决策流程表，靠 Claude 语言理解路由，无显式依赖
2. **Sequential Pipeline** — 线性流程（检索→分析→撰写→OA）
3. **Progressive Disclosure**（⭐⭐⭐⭐）— 主 skill 只加载 frontmatter（~100 tok），子 skill 懒加载；每个 ≤5000 行，共享预算 25k

**子 skill 间共享 context**：
- `references/shared-context.md` 作公共知识库
- 输出统一 JSON schema / markdown frontmatter
- 避免子 skill 互相直接调用，通过主 skill 汇聚

## 3. description 触发性写法

✅ 正例：`检索中国专利库中的现有技术。用户要求"检索相似专利"、"找先前技术"、"查询现有技术"，或提供发明技术方案需要验证新颖性时使用。`

❌ 反例：`专利检索工具`（无动词+无场景）

规则：
- 首句**动词**开头（检索/分析/撰写/答辩/验证）
- 含 3-5 个用户会说的关键词
- 追加 `when_to_use` 含 SKIP 条件
- description+when_to_use ≤ 1536 字符

## 4. 专利垂直工作流拆分原则（5 条）

1. **按工作流节点拆，不按工具拆**：`/patent-search` 聚合多源；不要为每个 API 单建 skill
2. **独立性优先**：子 skill 能单独工作，靠共享文件桥接，不靠运行时输出依赖
3. **上下文自主权**：主 skill 管"调度决策"，子 skill 管"执行指令"
4. **输出契约化**：统一 JSON schema / markdown frontmatter
5. **版本化**：把 skill 当代码，`allowed-tools` 明确权限边界

## 关键链接

- Skills 官方文档：https://code.claude.com/docs/en/skills
- anthropics/skills：https://github.com/anthropics/skills
- 深度解析：https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/
- 2026 实用指南：https://dev.to/muhammad_moeed/claude-code-skills-a-practical-guide-for-2026-3f6p
- Agentic AI Patent Search：https://ipwatchdog.com/2025/10/30/agentic-ai-meets-patent-search-new-paradigm-innovation/
