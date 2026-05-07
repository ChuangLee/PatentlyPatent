# PatentlyPatent

> **企业自助专利挖掘系统** · 员工 + Agent 协作 · 把工作中的创新变成可申请的专利

![status](https://img.shields.io/badge/status-WIP-orange)
![license](https://img.shields.io/badge/license-Apache--2.0-blue)
![python](https://img.shields.io/badge/python-3.10%2B-blue)

## ⚠️ 当前状态

**Work in progress · 不可用于生产**。本仓库正在从 v1（CNIPA 优先的专利全流程辅助 CLI）转向 v2（企业自助挖掘 Web 系统）。v1 代码（`pk/` 包）保留作为参考，v2 设计文档优先（`docs/requirements_v2.md`）。

## 目标

为企业员工提供"工作中发现创新 → 自助挖掘 → 出交底书"的浏览器自助平台：

1. 员工一句话描述工作创新
2. Agent 引导问询，把含糊的发现拆成结构化创新点
3. 调用专利数据源做现有技术筛查 + 初步专利性判断
4. 生成符合 CN 实务的中文交底书草稿，员工编辑后提交 IP 部门

## 设计理念

- **法条嵌入式 lint**：A22.3 三步法 / A26.3 充分公开 / A26.4 支持 / A33 修改超范围 / R20.2 必要技术特征 — 每个写入流程的关键节点
- **可锚定可追溯**：claim 中每个特征必须能锚回说明书原文与原始申请，可机械校验
- **专家心智显式化**：把"上位词的胆量""D1 重定义""R20.2 最小集"等代理师 know-how 显式编码为 prompt + 规则
- **可插拔数据源**：智慧芽 / Google Patents BigQuery / CNIPA / EPO OPS / USPTO ODP — adapter 接口统一

## 技术栈（v2 计划）

| 层 | 选型 |
|---|---|
| 前端 | Vue 3 + Ant Design Vue（Vue Vben Admin v5） |
| 后端 | FastAPI Best Architecture (FBA) v1.13+ |
| Agent | LangGraph + Anthropic SDK |
| 流式 | sse-starlette + @ai-sdk/vue |
| 编辑器 | Tiptap |
| 文档 | docxtpl + Pandoc |
| 存储 | PostgreSQL + Redis + MinIO + Meilisearch |
| 部署 | Docker Compose + Nginx |

详见 `ai_docs/oss_selection.md`。

## 项目结构

```
.
├── pk/                  # v1 Python 包（CNIPA 全流程 CLI 原型）
├── tests/               # v1 单元测试
├── docs/                # 需求 / 架构 / ADR
│   ├── requirements.md
│   ├── architecture.md
│   └── requirements_v2.md
├── ai_docs/             # 调研报告（LLM 工具/数据源/CN 实务/Skills/智慧芽 API/OSS 选型）
├── examples/            # 演示交底书样例
├── skills/              # Claude Skill 薄包装（v1）
└── refs/                # （不入仓）参考资料：3rd_repos + 专利专家知识库
```

## v1 快速试用（CLI，非生产）

```bash
pip install -e .
export ANTHROPIC_API_KEY=...
pk search --input examples/demo_invention.md -o search.json
pk draft  --input examples/demo_invention.md -s search.json -o draft.md
pk check  --input draft.md -o check_report.md
```

无 API key 也能演示：`PK_OFFLINE_DEMO=1 pk draft -i examples/demo_invention.md`。

## v2 路线（开发中）

- M1：智慧芽 adapter（官网 cookie + playwright）+ 数据模型 + 报门→检索单元跑通
- M2：FastAPI 后端骨架 + 认证 + 项目 CRUD + 流式 mining
- M3：完整 4 阶段 + 极简前端 + 端到端 demo
- M4：reviewer 审阅 + 导出 docx + 配额/审计

## 文档导航

- [v2 产品需求 (docs/requirements_v2.md)](./docs/requirements_v2.md)
- [OSS 选型决策 (ai_docs/oss_selection.md)](./ai_docs/oss_selection.md)
- [智慧芽 API 实测 (ai_docs/zhihuiya_api.md)](./ai_docs/zhihuiya_api.md)
- [CN 实务调研 (ai_docs/research_03_cn_practice.md)](./ai_docs/research_03_cn_practice.md)

## 贡献

WIP 阶段不接受 PR。设计稳定后会在 README 增加贡献指引。

## 许可

Apache License 2.0 · 见 [LICENSE](./LICENSE)
