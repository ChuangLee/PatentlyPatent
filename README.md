# PatentlyPatent

> **企业自助 AI 专利挖掘工作台** · 资深代理人级 AI 对话 + 检索 + 撰写 · 把一个含糊的发明点变成可交付代理所的中文交底书初稿

![python](https://img.shields.io/badge/python-3.12%2B-blue)
![frontend](https://img.shields.io/badge/frontend-Vue3%20%2B%20AntDV-4FC08D)
![llm](https://img.shields.io/badge/LLM-Claude%20Opus%204.7-6e3df7)
![license](https://img.shields.io/badge/license-Apache--2.0-blue)

公网入口：<https://blind.pub/patent>

## 它做什么

一名研发员工，用 1 小时左右：

1. **报门**：一段技术描述 + 可选 PDF/PPT/Word 附件
2. **附件归档完成后自动启动 interview-first 挖掘**：AI 边读资料边调研，问员工 ≤3 个关键事实/数据
3. **AI 自评素材足够** → 发 `[READY_FOR_WRITE]` 信号 → 自动并行写 5 章交底书初稿
4. **收尾确认 + 导出 docx**：员工拿到 `{发明名}-交底书.docx` 发给代理所

中间 AI 全程被注入「CN+US 双轨执业 10 年代理人」persona，硬性调研门槛 + 5 决策点 + A22/A26/R20.2 法条体检。

## 技术栈

| 层 | 选型 |
| --- | --- |
| 前端 | Vue 3 + Ant Design Vue + Pinia + Vite |
| 后端 | FastAPI + SQLAlchemy 2.0 + SQLite WAL |
| Agent | `claude-agent-sdk` + bundled Claude CLI（OAuth，不依赖 `ANTHROPIC_API_KEY`） |
| 主模型 | Claude Opus 4.7（撰写）+ Sonnet 4.6（light） |
| 流式 | Server-Sent Events，token 级 + tool_use_id 关联 + detached run 断线重连 |
| 编辑/预览 | Tiptap + marked GFM + mermaid + mammoth (docx) |
| 文档输出 | python-docx，5 章通用交底书结构 |
| 专利检索 | A 路 智慧芽托管 MCP（19 工具）+ B 路 Google Patents BigQuery（免费降级备选） |
| 鉴权 | JWT HS256 / 企业 CAS / bcrypt 真账密 |
| 部署 | systemd + nginx + Linux |

## A+B 双路专利检索

- **A 路（首选，收费）**：智慧芽托管 MCP — `patsnap_search` 关键词/语义检索、`patsnap_fetch` 拉权要/法律/同族、分类号助手、同义词扩展、申请人/语义/图像/嵌套相似检索等 19 个工具
- **B 路（降级备选，免费）**：Google Patents BigQuery `patents-public-data` — `bq_search_patents` / `bq_patent_detail`，CN 全量含中文译本
- A 路业务错（`67200004/05`）时 agent 自动切 B 路，SYSTEM_PROMPT 显式约束不重试

## 项目结构

```
.
├── frontend/                    # Vue3 SPA
├── backend/                     # FastAPI + Agent
│   ├── app/
│   │   ├── agent_interview.py   # interview-first 状态机
│   │   ├── agent_sdk_spike.py   # SDK 适配 + in-process MCP server
│   │   ├── agent_section_demo.py # 5 节 section prompts
│   │   ├── patents_bq.py        # B 路 BigQuery adapter
│   │   ├── zhihuiya.py          # in-house 智慧芽 REST 兜底
│   │   ├── disclosure_no34.py   # docx 模板
│   │   ├── routes/              # 11 个 FastAPI router
│   │   └── ...
│   ├── storage/                 # 项目附件 + 导出 docx
│   └── patentlypatent.db        # SQLite WAL
├── docs/                        # 4 篇正式文档（README 串目录）
│   ├── prd.md
│   ├── hld.md
│   ├── user_guide.md
│   └── deploy_runbook.md
├── refs/                        # （不入 git）参考资料
│   └── 专利专家知识库/           # 419 篇 CN 实务知识库（kb）
├── ai_docs/                     # 调研稿
└── .secrets/                    # （不入 git）凭证
    ├── zhihuiya.env             # REST token + 托管 MCP URLs
    └── gcp-bq.json              # B 路 BigQuery service account
```

## 文档导航

- [docs/README.md](./docs/README.md) — 文档总览
- [docs/user_guide.md](./docs/user_guide.md) — 员工用户手册（5 步出交底书）
- [docs/prd.md](./docs/prd.md) — 产品需求文档（做什么 / 给谁 / 衡量什么 / 路线图）
- [docs/hld.md](./docs/hld.md) — 高层设计（C4 三层 / 数据模型 / SSE 协议 / MCP 拓扑 / 安全 / 可观测）
- [docs/deploy_runbook.md](./docs/deploy_runbook.md) — 部署运维手册（systemd / nginx / CLI 认证 / BigQuery 启用 / CAS / 紧急处理）

## 设计理念

- **interview-first** 而非 generate-first：先问清楚到 AI 自评素材足够，再开写
- **信号驱动状态机**：流程跃迁靠 AI 在文本里显式输出 `[READY_FOR_WRITE]` 等信号，不靠字数/章数等 heuristic
- **企业可控**：所有 LLM 走 claude CLI OAuth；员工资料不出企业内网
- **可观测 + 可治理**：每次 agent 调用入 `AgentRunLog`；admin Dashboard 看 cost / fallback / error；日预算阻断（warn $2 / block $10）
- **harness 层兜底**：plan diff 自动派生 `step_done` / `step_failed` 气泡，不依赖 LLM 自觉叙述
- **断线必可恢复**：detached SSE run + event_id 增量重放

## 文档自同步

启动期 `system_docs.backfill_all_projects()` 把上述 4 篇正式文档幂等推到每个项目的「📖 本系统文档」只读根目录，员工在工作台文件树即可查 PRD / HLD / 使用手册 / 部署手册。

## 贡献

企业内部部署阶段，暂不接受外部 PR。

## 许可

Apache License 2.0 · 见 [LICENSE](./LICENSE)
