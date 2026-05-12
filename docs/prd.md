# patent_king 产品需求文档

> 更新于 2026-05-12 · 配套：[`hld.md`](./hld.md) · [`user_guide.md`](./user_guide.md) · [`deploy_runbook.md`](./deploy_runbook.md)

---

## 目录

- [1. 产品定位与宣言](#1-产品定位与宣言)
- [2. 目标用户画像与权限](#2-目标用户画像与权限)
- [3. 用户旅程图](#3-用户旅程图)
- [4. 用例图](#4-用例图)
- [5. 功能模块清单](#5-功能模块清单)
- [6. 信号驱动的状态机](#6-信号驱动的状态机)
- [7. 关键业务流程图](#7-关键业务流程图)
- [8. 非功能需求](#8-非功能需求)
- [9. 关键 KPI](#9-关键-kpi)
- [10. 产品边界（不做什么）](#10-产品边界不做什么)
- [11. 风险与缓解](#11-风险与缓解)
- [12. 路线图](#12-路线图)
- [13. 决策日志与开放问题](#13-决策日志与开放问题)

---

## 1. 产品定位与宣言

### 1.1 一句话宣言

> **patent_king 是企业内部的 AI 专利挖掘工作台：让任何一名研发员工都能在 1 小时内，与资深代理人级 AI 对话，把一个含糊的发明点变成可交付代理所的中文交底书初稿。**

### 1.2 定位象限

| 维度 | patent_king | 传统流程 | 通用 ChatGPT |
| --- | --- | --- | --- |
| **目标用户** | 企业研发员工（非专代） | 专利代理人 | 通用知识工作者 |
| **流程闭环** | 报门 → 对话挖掘 → 写章节 → 导出 docx | 员工报 idea → 等代理人来访 → 数周回稿 | 单 turn 问答，无项目化 |
| **数据源** | 智慧芽 API + 419 篇 CN 专家知识库 + 上传材料 | 个人经验 + 散点检索 | 训练截止前公开数据 |
| **AI 角色** | 资深 CN+US 双轨执业 10 年代理人 persona | 真人代理人 | 无明确 persona |
| **输出** | 5 节结构化中文交底书 docx + 全程对话存档 | 申请书 / OA 答复 | 自由文本 |
| **可观测** | AgentRunLog + admin Dashboard + 日预算阻断 | 邮件 + 工时表 | 无 |

### 1.3 产品哲学

1. **降低专利写作门槛**：员工不需要懂 35 USC § 102/103 或专利法第 22 条，只需描述「我做了什么、解决什么问题」，AI 把法言法语翻译过来。
2. **interview-first 而非 generate-first**：不让 AI 一上来就胡编 5 章——先问清楚，问到 AI 自评「素材够了」才发 `[READY_FOR_WRITE]` 信号触发写作。
3. **信号驱动状态机**：流程跃迁由 AI 显式信号触发，不靠定时/字数/章节计数等 heuristic。
4. **企业可控**：所有 LLM 走 claude CLI OAuth，所有数据走智慧芽 API + 内部 SQLite，不依赖个人 API key，不外发员工资料。
5. **AI 不替代专代审核**：输出叫「交底书初稿」而不是「申请文件」，必须经专代/IP 律师人工审核。

---

## 2. 目标用户画像与权限

### 2.1 三类角色总览

| 角色 | 系统标识 | 典型画像 | 占比预估 |
| --- | --- | --- | --- |
| **企业研发员工** | `employee` | 28-40 岁，硕士/博士，研发/算法/产品工程师，1 年内有 ≥1 个可申请发明点 | 95% |
| **知识库管理员** | `kb_admin` | IP 律师 / 资深专代 / 技术总监，负责维护 419 篇专家知识库与企业内部范本 | 3% |
| **系统管理员** | `admin` | 运维 / 研发负责人，关注 SSE 并发、cost、fallback、错误监控 | 2% |

### 2.2 权限矩阵

| 能力 | employee | kb_admin | admin |
| --- | --- | --- | --- |
| 登录（JWT / CAS / 真账密） | Y | Y | Y |
| 报门创建项目 | Y | Y | Y |
| 查看 / 编辑自己的项目 | Y（仅自己） | Y（仅自己） | Y（全部，只读） |
| Agent 对话挖掘 | Y | Y | Y |
| 文件上传 / 文件树管理 | Y | Y | Y |
| **kb「📚 专利知识」浏览** | Y（只读） | Y（只读） | Y（只读） |
| **kb 编辑 / 上传 / 删除** | N | Y | Y |
| **本系统文档只读浏览**（P1） | N | N | Y |
| 导出 docx | Y | Y | Y |
| admin Dashboard | N | N | Y |
| A/B 对比 / N 次回归探针 | N | N | Y |
| 切 agent_sdk 模式 / 日预算配置 | N | N | Y |
| 查看他人 AgentRunLog | N | N | Y |

> **当前实现状态（2026-05-12）**：employee / admin 已落地；kb_admin 为本 v2 新增角色，v0.37 实装（见路线图）。

### 2.3 典型画像（Persona）

#### 画像 A：张工，算法工程师，3 年司龄

- 上个月在内部 OKR 复盘里被 leader 点名："你那个动态调参算法可以申个专利"。
- 痛点：不知道交底书长啥样、没时间读现有专利、不懂权利要求怎么写。
- 期望：1 小时内能交付一份让代理所「能开始干活」的初稿。

#### 画像 B：李律师，企业 IP 部，资深代理人，10 年司龄

- 痛点：员工提交的交底书参差不齐，要返工 3-5 轮才能进申请阶段。
- 期望：能在 kb 里上传企业内部的标杆案例 / 撰写规范 / 行业范本，让 AI 直接引用。

#### 画像 C：王经理，研发部部门长

- 痛点：不知道部门下属每月产出多少 idea，哪些方向值得投资。
- 期望：admin Dashboard 看到全员 cost / 完整挖掘率 / 进入 docx 阶段的比例。

---

## 3. 用户旅程图

### 3.1 张工的端到端旅程（从拿到链接到收 docx）

```mermaid
journey
    title 张工首次使用 patent_king（90 分钟）
    section 触达与登录
      收到企业邮件链接: 4: 张工
      点开 blind.pub/patent: 4: 张工
      企业 CAS 单点登录: 5: 张工
      看到 6 步教程引导: 5: 张工
    section 报门
      新建项目填发明名称: 4: 张工
      粘贴 200 字技术描述: 3: 张工
      拖入 3 个 PDF 参考: 5: 张工
      看到 上传进度条 N/3: 5: 张工
      点 创建项目: 5: 张工
    section 等附件归档
      等待 收到附件 提示: 3: 张工
      看到 文件树自动出现 3 个 PDF: 5: 张工
    section interview-first 挖掘
      AI 问 你这个算法解决什么具体场景: 4: 张工
      回答 在线广告竞价低延迟: 5: 张工
      AI 问 现有方案问题点是什么: 4: 张工
      回答 现有 LR 模型不收敛: 5: 张工
      AI 又问 5 个问题: 3: 张工
      AI 发出 READY_FOR_WRITE 信号: 5: 张工
      自动触发 mineFull 5 章写作: 5: 张工
    section 收尾与导出
      AI 提示 还需要确认 3 个 claim 措辞: 4: 张工
      逐一确认: 4: 张工
      AI 发出 READY_FOR_DOCX 信号: 5: 张工
      点 导出 docx: 5: 张工
      下载 张工-动态调参-交底书.docx: 5: 张工
      发邮件给代理所: 5: 张工
```

### 3.2 旅程关键愉悦点 vs 痛点

| 阶段 | 愉悦点（产品要强化） | 痛点（产品要消解） |
| --- | --- | --- |
| **登录** | CAS 一键 SSO，不用记新密码 | dev role 切换暴露在生产（已修复 v0.26） |
| **报门** | 拖拽 N 个 PDF + 实时进度 N/total | 上传慢、不知道传完没（v0.35 加 「附件归档完成」提示） |
| **interview-first** | AI 像真代理人在问细节，员工有被「认真对待」感 | 早期版本 AI 直接生成，被员工反馈「胡编」（v0.30 修复） |
| **写章节** | 5 章并行 SSE 流式，看着字一行行涌出来 | 期间断线 → 之前白跑（v0.36 detached run 修复） |
| **收尾** | 答疑能自动写回 md，不用复制粘贴 | claim 措辞有时拗口，员工不敢动（P1：撰写阶段多轮迭代） |
| **导出** | docx 一键下载、46K、Word 直接打开 | 模板曾用「No.34 科技进步奖」不合专利实务（v0.34 换 5 章交底书模板） |

---

## 4. 用例图

```mermaid
flowchart TB
    classDef actor fill:#e0e7ff,stroke:#5b6cff,stroke-width:2px,color:#1e1b4b
    classDef uc fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef system fill:#dcfce7,stroke:#16a34a,color:#14532d

    Employee([员工<br/>employee]):::actor
    KbAdmin([知识库管理员<br/>kb_admin]):::actor
    Admin([系统管理员<br/>admin]):::actor
    CAS([企业 CAS<br/>外部系统]):::system
    Zhihuiya([智慧芽 API<br/>外部系统]):::system
    ClaudeCLI([Claude CLI<br/>外部系统]):::system

    UC1[登录 JWT/CAS/真账密]:::uc
    UC2[报门：填发明 + 上传附件]:::uc
    UC3[等附件归档]:::uc
    UC4[interview-first 对话挖掘]:::uc
    UC5[自动 mineFull 写 5 章]:::uc
    UC6[收尾确认 + 答疑回填]:::uc
    UC7[导出 docx 交底书]:::uc
    UC8[浏览自己的项目文件树]:::uc
    UC9[预览 pdf/docx/pptx/md/json]:::uc
    UC10[浏览 kb 专利知识库 419 篇]:::uc

    UC11[维护 kb：上传/编辑/删除]:::uc
    UC12[维护本系统文档只读根]:::uc

    UC13[查看 admin Dashboard]:::uc
    UC14[监控 AgentRunLog/cost/fallback/error]:::uc
    UC15[N 次回归探针]:::uc
    UC16[A/B 对比 legacy vs agent]:::uc
    UC17[配置日预算/SSE 限流]:::uc
    UC18[切 agent_sdk 模式]:::uc

    Employee --> UC1
    Employee --> UC2
    Employee --> UC3
    Employee --> UC4
    Employee --> UC5
    Employee --> UC6
    Employee --> UC7
    Employee --> UC8
    Employee --> UC9
    Employee --> UC10

    KbAdmin --> UC1
    KbAdmin --> UC10
    KbAdmin --> UC11
    KbAdmin -.可选.-> UC2

    Admin --> UC1
    Admin --> UC12
    Admin --> UC13
    Admin --> UC14
    Admin --> UC15
    Admin --> UC16
    Admin --> UC17
    Admin --> UC18

    UC1 -.SAML/XML.-> CAS
    UC4 -.LLM 调用.-> ClaudeCLI
    UC5 -.LLM 调用.-> ClaudeCLI
    UC5 -.专利数据.-> Zhihuiya
    UC4 -.专利数据.-> Zhihuiya
```

---

## 5. 功能模块清单

### 5.1 P0 — 已上线（v0.36 当前生产）

| # | 模块 | 子能力 | 落地版本 | 状态 |
| --- | --- | --- | --- | --- |
| F-01 | **登录** | JWT 真账密 + CAS SSO + dev role（仅 DEV） | v0.21 / v0.23 / v0.28 | ✅ |
| F-02 | **报门** | 多文件拖拽 + 进度条 N/total + 阶段卡片 + 3 根 folder 自动建 | v0.5 / v0.10 / v0.14 | ✅ |
| F-03 | **附件归档等待** | 上传完成才启动 agent，避免读不到资料 | v0.35 | ✅ |
| F-04 | **interview-first 挖掘** | 先问后写；AI 自评素材足够才发 `[READY_FOR_WRITE]` | v0.30 | ✅ |
| F-05 | **mineFull 5 章自动写作** | 信号触发；prior_art / summary / embodiments / claims / drawings_description 5 节并行 SSE | v0.20 / v0.31 | ✅ |
| F-06 | **答疑回填** | answer_router 5 类关键词分发，写回对应 md H2 锚点 | v0.13 | ✅ |
| F-07 | **docx 导出** | python-docx 5 章交底书模板（v0.34 替换 No.34）；`{title}-交底书.docx` | v0.7 / v0.34 | ✅ |
| F-08 | **文件树** | 我的资料 / AI 输出 / .ai-internal(hidden) / 📚 专利知识 | v0.10 / v0.22 | ✅ |
| F-09 | **文件预览** | pdf / docx / pptx / md / json / 图片 inline | v0.11 / v0.27 | ✅ |
| F-10 | **kb 只读浏览** | 419 文件 / 37 子目录 / 92.7MB；mutate 守卫 | v0.22 | ✅ |
| F-11 | **资深代理人 persona** | CN+US 双轨执业 10 年；prompt 注入 419 篇 kb 索引 | v0.34 | ✅ |
| F-12 | **SSE 流 + 断线恢复** | detached run；前端断线重连 ?from=N | v0.36 | ✅ |
| F-13 | **SSE 限流** | Semaphore(5)；超限 503 | v0.21 | ✅ |
| F-14 | **日预算阻断** | warn $2 / block $10；update_after_run 聚合 | v0.21 | ✅ |
| F-15 | **admin Dashboard** | 8 卡片：项目状态饼 / 评分柱 / agent_runs / cost 时序 / fallback / error 24h / A-B / 预算 | v0.21–v0.36 | ✅ |
| F-16 | **AgentRunLog** | 每次 agent 调用入库：endpoint / cost / duration / fallback / error | v0.19 | ✅ |
| F-17 | **6 步使用教程组件** | 首次登录顶部引导 | v0.26 | ✅ |

### 5.2 P1 — 下一季度（v0.37 → v0.39）计划

| # | 模块 | 子能力 | 目标版本 | 优先级 |
| --- | --- | --- | --- | --- |
| F-18 | **本系统文档只读根** | admin 在文件树根部看到 `docs/` 只读，方便随时查 PRD/HLD/runbook | v0.37 | 高（用户刚要求）|
| F-19 | **kb_admin 角色 + kb 写权限** | RBAC 增加 kb_admin；kb 节点开放上传/编辑/删除 | v0.37 | 高 |
| F-20 | **检索阶段（智慧芽精检）** | 在 interview-first 与 mineFull 之间增加「精检」步骤：基于已挖掘的关键词、IPC、申请人组合查重 | v0.38 | 高 |
| F-21 | **撰写阶段多轮迭代修订** | 写完一章后允许员工说「这段太长 / 用另一种实施例」，AI 局部重写不重跑全章 | v0.38 | 高 |
| F-22 | **专利性初判报告** | 检索阶段后自动生成「新颖性 / 创造性」初判 markdown，标 X/Y/N 文献 | v0.38 | 中 |
| F-23 | **Sentry + cron 备份** | 错误监控 + sqlite 每日备份 | v0.37 | 中 |
| F-24 | **真用户库 + CAS 联调** | 取代 u1/u2 fixture；员工首次 SSO 自动建 user 行 | v0.37 | 中 |
| F-25 | **a11y + 移动端 375/768** | Lighthouse a11y > 90；响应式 token 已就位，待真机扫 | v0.39 | 低 |

### 5.3 P2 — 远景（v0.40+）视野

| # | 模块 | 子能力 | 说明 |
| --- | --- | --- | --- |
| F-26 | **多语言**（EN 交底书） | US persona 已就位；US 专代要 EN 版 disclosure | 双语模板切换 |
| F-27 | **多 agent 协作** | 检索 agent + 撰写 agent + 审查 agent 三角；employee 看到合议过程 | 类似 AutoGen / CrewAI 风格 |
| F-28 | **团队共享** | 同部门员工可只读他人项目；leader 可批量看本组挖掘进展 | RBAC + 部门字段 |
| F-29 | **OA 答复辅助** | 上传审查意见 → AI 出答辩思路 + 修改建议 | 与原 disclosure 联动 |
| F-30 | **专代审核闭环** | kb_admin 在 docx 上批注 → 回到 web UI → 员工逐条改 | 二审闭环 |

---

## 6. 信号驱动的状态机

### 6.1 设计原理

传统 agent 流程靠「字数 / 章节数 / 轮次」等 heuristic 触发跃迁，容易出现：

- 员工还没说清楚就开写 → 章节空洞；
- 员工已经说完了但 AI 还在追问 → 体验拖沓；
- 5 章写完了但其实没收尾 → 直接出 docx 漏 claim 校验。

**v0.31 起改为「信号驱动」**：AI 在 prompt 里被显式约束「当且仅当 X 时输出信号 Y」，后端 SSE 流监听到信号原文则触发对应跃迁。

| 信号 | 含义 | 触发后端动作 |
| --- | --- | --- |
| `[READY_FOR_WRITE]` | AI 自评：interview 已收集足够素材，可以开始写 5 章 | 自动 POST `/api/agent/mine_full/{pid}` SSE |
| `[READY_FOR_DOCX]` | AI 自评：5 章已写完 + 收尾确认完成，可以导出 | 前端 docx 导出按钮变可点击 + 推一条系统消息 |
| `[NEED_USER_INPUT]` | AI 等用户答复，暂不前推 | 前端 chat 输入框 focus |
| `[FALLBACK]` | agent 链路失败兜底到 mining.py legacy | 后端记录 AgentRunLog.fallback=True |

### 6.2 状态机图

```mermaid
stateDiagram-v2
    [*] --> drafting: 报门创建项目

    drafting --> attachments_uploading: 选择附件
    attachments_uploading --> attachments_ready: 所有附件落盘
    drafting --> attachments_ready: 无附件直接跳过

    attachments_ready --> interview: 用户首次进入工作台
    interview --> interview: AI 提问 + 用户回答<br/>(NEED_USER_INPUT 循环)
    interview --> writing: AI 发出 [READY_FOR_WRITE]

    writing --> writing_prior_art: 节 1
    writing_prior_art --> writing_summary: 节 1 done
    writing_summary --> writing_embodiments: 节 2 done
    writing_embodiments --> writing_claims: 节 3 done
    writing_claims --> writing_drawings: 节 4 done
    writing_drawings --> writing_done: 节 5 done

    writing_done --> finalize: 进入收尾
    finalize --> finalize: 答疑回填<br/>claim 措辞确认
    finalize --> ready_docx: AI 发出 [READY_FOR_DOCX]

    ready_docx --> docx_exported: 用户点导出
    docx_exported --> [*]

    writing --> fallback: 任一章 [FALLBACK]
    fallback --> writing_done: legacy 占位骨架填齐
    fallback --> finalize

    interview --> archived: 用户主动归档
    writing --> archived: SSE 断线 detached run
    archived --> interview: 用户回来重连 ?from=N
```

### 6.3 信号实战示例

**interview-first 阶段 AI prompt 片段**（节选）：

```
你是资深 CN+US 双轨执业 10 年代理人。
你的任务：通过追问把员工模糊的发明点拆成 5 章交底书可用的素材。
约束：
- 每轮最多问 3 个问题
- 当且仅当你判断「问题领域 / 技术问题 / 技术方案 / 至少 1 个实施例 / 与现有技术区别」5 个维度都收齐时，
  最后一行输出 [READY_FOR_WRITE]
- 收齐前禁止输出 [READY_FOR_WRITE]
- 如果用户说「我没了，你写吧」但素材实际不足，应继续追问而不是写
```

后端 SSE 中间件按行扫 `if "[READY_FOR_WRITE]" in line: trigger_mineFull(project_id)`。

---

## 7. 关键业务流程图

### 7.1 报门到导出主流程

```mermaid
flowchart TD
    A[员工 CAS 登录] --> B[新建项目<br/>填发明名 + 描述 + 拖拽附件]
    B --> C[POST /api/projects]
    C --> D[后端建 3 根 folder + 异步收附件]
    D --> E{所有附件落盘?}
    E -->|否| E1[前端轮询<br/>显示 上传中 N/total]
    E1 --> E
    E -->|是| F[跳转 ProjectWorkbench]
    F --> G[启动 interview SSE]
    G --> H[AI 资深代理人 persona 加载<br/>注入 419 篇 kb 索引]
    H --> I[AI 第一问]
    I --> J[用户答 + chat 持久化]
    J --> K{AI 自评素材足?}
    K -->|否 NEED_USER_INPUT| I
    K -->|是 READY_FOR_WRITE| L[后端自动 POST mine_full]
    L --> M[5 章 SSE 并行]
    M --> N[file_write_section 落盘 + .ai-internal/_compare/]
    N --> O[finalize 收尾对话]
    O --> P{claim 措辞确认完?}
    P -->|否| O
    P -->|是 READY_FOR_DOCX| Q[前端 docx 按钮变亮]
    Q --> R[用户点导出]
    R --> S[python-docx 5 章模板渲染]
    S --> T[下载 title-交底书.docx]
    T --> U[员工发代理所]
```

### 7.2 SSE 断线恢复

```mermaid
sequenceDiagram
    autonumber
    participant FE as 前端 Vue
    participant BE as FastAPI
    participant DB as SQLite agent_runs

    FE->>BE: POST /agent/mine_full SSE
    BE->>BE: 启动 detached task
    BE->>DB: INSERT run_id, start_at
    BE-->>FE: SSE event_id=1 thinking
    BE-->>FE: SSE event_id=2 tool_use
    Note over FE,BE: 网络断
    BE-->>BE: 后台继续跑
    BE->>DB: UPDATE run_id 各 event
    FE->>FE: 检测 SSE 断
    FE->>BE: GET /agent/runs/{rid}?from=2
    BE->>DB: SELECT events WHERE id > 2
    BE-->>FE: SSE event_id=3..N 重放
    BE-->>FE: SSE done
    FE-->>FE: 文件树自动刷新
```

### 7.3 双轨：legacy mining vs agent path

```mermaid
graph LR
    subgraph Legacy[mining.py 老路径]
        L1[关键词抽取] --> L2[zhihuiya 直调]
        L2 --> L3[占位骨架填表]
        L3 --> L4[5 节占位 .md]
    end
    subgraph Agent[Agent SDK 真路径]
        A1[ClaudeAgentOptions + 8 tools] --> A2[LLM 自驱循环]
        A2 --> A3{需要数据?}
        A3 -->|是| A4[tool_use → 智慧芽/DB/write]
        A4 --> A2
        A3 -->|否 done| A5[delta 流式]
    end
    Compare[A/B 对比落盘<br/>.ai-internal/_compare/full/]
    L4 --> Compare
    A5 --> Compare
    Compare --> Admin[admin Dashboard<br/>双 markdown 并列]
```

---

## 8. 非功能需求

### 8.1 性能

| 指标 | 阈值（p95） | 当前实测 | 测量位置 |
| --- | --- | --- | --- |
| 首屏 LCP | < 2.0s | 1.6s（v0.16 拆包后） | 公网 Lighthouse |
| 首屏体积（gzip） | < 300KB | 250KB | vite build report |
| 报门接口耗时 | < 800ms | 320ms | 后端 access log |
| interview 首字延迟 | < 3s | 2.1s（cache 命中后） | SSE first byte |
| **5 节 mineFull 端到端** | **< 120s p95** | 92s（v0.34 实测） | agent_runs.duration_ms |
| docx 导出耗时 | < 5s | 1.8s | python-docx 耗时 |
| kb 文件预览首字 | < 1s | 0.4s | preview SSE |

### 8.2 可靠性

| 维度 | 要求 | 实现 |
| --- | --- | --- |
| **SSE 断线可恢复** | 任意时刻断线，重连可补齐未消费 events | v0.36 detached run + event_id 增量 |
| **fallback 兜底** | 任一节 agent 失败 → 自动 fallback 到 legacy 占位骨架，员工流程不中断 | mining.py legacy + AgentRunLog.fallback 标记 |
| **服务自愈** | 进程 crash 后 systemd auto-restart < 5s | deploy_runbook.md `systemd` section |
| **数据持久化** | sqlite WAL 模式 + 每日 cron 备份 | v0.13（WAL）+ v0.37 计划（cron） |
| **附件归档保证** | agent 启动前确认所有 attachment 落盘 | v0.35 前置 wait |

### 8.3 安全

| 维度 | 要求 | 实现 |
| --- | --- | --- |
| **认证** | JWT HS256 / 企业 CAS / 真账密 bcrypt 三选一 | v0.21 / v0.23 / v0.28 |
| **授权** | RBAC：employee 只看自己项目；admin 只读全部 | FastAPI Depends 校验 |
| **文件路径 sanitize** | resolve 后 `startswith(ROOT)` 防 `../` | kb / 项目 file API 通用 |
| **上传大小限制** | 单文件 ≤ 50MB；kb 单文件 ≤ 5MB | nginx client_max_body + 后端校验 |
| **LLM 凭证** | 走 claude CLI OAuth；**禁止** ANTHROPIC_API_KEY | systemd PATH+HOME override |
| **智慧芽 token** | 存 `.secrets/zhihuiya.env`，git ignore；后端读 env | deploy_runbook.md |
| **CAS XML 安全** | defusedxml 解析，防 XXE | v0.23 |
| **CORS** | 仅允许 blind.pub 域 | nginx + FastAPI middleware |

### 8.4 可观测

| 维度 | 实现 |
| --- | --- |
| **AgentRunLog 表** | 每次 agent 调用入库：endpoint / cost_usd / duration_ms / num_turns / fallback / error / model |
| **admin Dashboard 8 卡片** | 项目状态饼 / 评分柱 / agent_runs 表 / cost 时序 / fallback 率柱 / error 24h / A-B 对比 / budget_status |
| **结构化日志** | uvicorn access log + 业务 logger（INFO/WARN/ERROR） |
| **budget_status 端点** | sse_in_flight / daily_sum / daily_block 实时 |
| **Sentry**（P1） | v0.37 接入，错误自动告警 |

### 8.5 成本

| 项 | 阈值 | 实现 |
| --- | --- | --- |
| **日预算总上限** | $10 / day（block）；$2 / day（warn） | `PP_DAILY_BUDGET_BLOCK` / `_WARN` env |
| **单次 5 节挖掘** | < $0.5 | 实测 $0.034 mock / $0.21 真路径（cache miss）/ $0.084（cache hit） |
| **prompt cache 命中节省** | ≥ 50% | 实测 60%（SystemPromptPreset.exclude_dynamic_sections=True） |
| **超限处理** | 503 拒绝新 SSE，已跑的 run 继续 | budget middleware |

---

## 9. 关键 KPI

### 9.1 北极星指标

| KPI | 定义 | 目标 | 当前 |
| --- | --- | --- | --- |
| **员工 NPS** | 「你会推荐给同事用 patent_king 吗？」9-10 分占比 - 0-6 分占比 | ≥ 40 | 待真用户采样（v0.37 起） |

### 9.2 一级指标

| KPI | 定义 | 目标 | 当前实测 |
| --- | --- | --- | --- |
| **完整挖掘率** | 报门项目中走到 `[READY_FOR_DOCX]` 的比例 | ≥ 70% | dry-run 框架已就位 |
| **平均挖掘 cost** | agent_runs 按项目聚合的 cost_usd 中位数 | < $0.3 | $0.21（cache miss） |
| **docx 一次通过率** | docx 导出后员工不再回到 finalize 修改的比例 | ≥ 60% | 待采样 |
| **fallback 率** | AgentRunLog.fallback=True / 总次数 | < 30% | 0%（v0.19 起稳定） |

### 9.3 二级指标

| KPI | 定义 | 目标 | 当前 |
| --- | --- | --- | --- |
| 5 节挖掘 p95 耗时 | duration_ms 95 分位 | < 120s | 92s |
| SSE 并发上限 | Semaphore | 5 | 5 |
| 日预算阻断触发次数 | budget block / day | 0（理想） | 0 |
| 后端单测 | pytest pass | 100% | 100% |
| 前端单测 | vitest pass | 100% | 100%（44/44） |
| Lighthouse a11y | score | > 90 | 待 v0.39 |

---

## 10. 产品边界（不做什么）

| 边界 | 理由 |
| --- | --- |
| **不替代专代最终审核** | 输出叫「交底书初稿」，必须人工二审；UI 上每个 docx 导出页都有声明 |
| **不直接对外提交 CNIPA/USPTO** | 不做电子申请通道；员工拿 docx 走代理所 |
| **不存敏感个人数据** | 不收集身份证 / 手机号 / 薪资；仅用工号 + 邮箱（CAS attribute） |
| **不做向量检索 / embedding** | 用户明确反馈不做（memory `feedback_no_vector_search`）；走智慧芽关键字 |
| **不做多租户隔离**（当前） | 单企业自助系统；P2 才考虑 cache 隔离 |
| **不做工单审批流** | 不做「员工 → leader 审批 → IP 立项」链路；员工自决 |
| **不维护自营专利爬虫** | 全走智慧芽 API |
| **不抓微信公众号** | mp.weixin.qq.com 抓不到（HIP 也不行），靠转载源 |
| **不做 Playwright UI e2e** | 当前 pytest + vitest + 公网烟测试足够 |
| **不绑定 ANTHROPIC_API_KEY** | LLM 必须走 claude CLI OAuth，企业可控 |

---

## 11. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| **LLM 幻觉写出错误专利分类号** | 中 | 高（误导员工） | persona 强约束 + kb 419 篇范本 + admin Dashboard fallback 监控 + docx 显式 disclaimer |
| **claude CLI OAuth 凭证过期** | 中 | 高（全站 LLM 失效） | deploy_runbook.md 续期 SOP + Sentry 告警（v0.37） |
| **智慧芽 API 限流 / 改字段** | 中 | 中 | 6 端点 TTL cache（10s）+ 降级到 keyword-only fallback + 适配层封装 |
| **SSE 长连接被 nginx/网关切断** | 中 | 中 | nginx proxy_buffering off + detached run + 重连 ?from=N |
| **员工上传敏感商业秘密外泄** | 低 | 高 | 全程不出企业内网 + LLM 走 claude CLI（无第三方 SDK 中转）+ 文件 sanitize |
| **日 cost 超 $10 击穿** | 低 | 中 | budget block 硬阻断 + warn $2 早期预警 + admin 可调 env |
| **kb 知识库 419 篇内容过时** | 高 | 低 | kb_admin 角色（v0.37）支持增量更新；prompt 不全文注入只注索引 |
| **真用户 SSO 集成失败** | 中 | 高 | CAS XML 解析路径已 v0.23 跑通；保留 JWT 真账密兜底 |
| **5 章模板与实际代理所偏好不符** | 中 | 中 | v0.34 已替换为通用 5 章；P1 让 kb_admin 自定义 docx 模板 |

---

## 12. 路线图（v0.37 → v0.40）

### 12.1 季度规划甘特图

```mermaid
gantt
    title patent_king 2026 Q2/Q3 路线图
    dateFormat YYYY-MM-DD
    section 已交付
    v0.5-v0.28 MVP+CAS+设计系统  :done, m1, 2026-05-07, 2d
    v0.29-v0.33 信号驱动状态机    :done, m2, 2026-05-09, 3d
    v0.34-v0.36 资深 persona+detached run  :done, m3, 2026-05-10, 3d

    section v0.37 上线护栏
    本系统文档只读根              :crit, v37a, 2026-05-13, 2d
    kb_admin 角色 + RBAC          :v37b, after v37a, 3d
    Sentry + cron 备份            :v37c, after v37a, 2d
    真用户库 + CAS server 联调    :v37d, after v37b, 4d

    section v0.38 检索+撰写迭代
    检索阶段（智慧芽精检）        :v38a, after v37d, 4d
    专利性初判报告                :v38b, after v38a, 3d
    撰写阶段多轮迭代修订          :v38c, after v38a, 5d

    section v0.39 体验
    a11y + 移动端 375/768         :v39a, after v38c, 5d
    micro-interaction + 拖拽过渡  :v39b, after v39a, 3d

    section v0.40 远景
    多语言 EN disclosure          :v40a, after v39b, 7d
    多 agent 协作                 :v40b, after v40a, 10d
    团队共享 + 部门 RBAC          :v40c, after v40b, 7d
```

### 12.2 版本验收门槛

| 版本 | 范围 | 验收标准 | 预计完成 |
| --- | --- | --- | --- |
| **v0.37 上线护栏** | 本系统文档只读根 / kb_admin / Sentry / cron 备份 / 真用户库 | (1) admin 文件树看到 `docs/` 只读 (2) kb_admin 能上传 (3) Sentry 收到 ≥ 1 条错误 (4) cron 备份每日跑 (5) 5 个真员工 CAS 登陆成功 | 2026-05-25 |
| **v0.38 检索+撰写迭代** | 智慧芽精检阶段 / 专利性初判 / 章节局部重写 | (1) interview 后自动出精检报告 (2) 报告含 ≥ 5 篇 X/Y/N 标注 (3) 员工可对单章说「重写更短版」 | 2026-06-15 |
| **v0.39 体验** | a11y / 移动端 / micro-interaction | Lighthouse a11y > 90；375px 单栏 OK；新教程动画 | 2026-07-10 |
| **v0.40 多语言+多 agent** | EN disclosure 模板 / 三 agent 合议 / 部门共享 | (1) 可生成 EN docx (2) 员工看到「检索 agent + 撰写 agent + 审查 agent」分工 (3) leader 可看本组项目列表 | 2026-08-30 |

---

## 13. 决策日志与开放问题

### 13.1 已决策（精选）

| ID | 决策 | 时点 | 理由 |
| --- | --- | --- | --- |
| D-1 | 走 Claude Agent SDK 而非直调 Anthropic API | v0.16 | tool 自驱 + 多 turn 内置；少量 @tool 装饰即可 |
| D-2 | claude CLI OAuth 替代 ANTHROPIC_API_KEY | v0.18 | 企业可控；systemd PATH+HOME override |
| D-3 | 信号驱动状态机替代 heuristic | v0.31 | 避免章数 / 字数 / 轮次的脆弱判断 |
| D-4 | interview-first 替代 generate-first | v0.30 | 用户反馈「AI 一上来就胡编」 |
| D-5 | 5 章交底书模板替代 No.34 科技进步奖模板 | v0.34 | No.34 是项目申报模板，不符专利实务；改资深代理人通用 5 章 |
| D-6 | detached SSE run + ?from=N 恢复 | v0.36 | 长流程断网必然发生，必须可恢复 |
| D-7 | 附件归档等待前置 | v0.35 | 早期版本 agent 启动时附件还没传完，读不到 → 报错 |
| D-8 | kb 419 篇只读 + 不入向量库 | v0.22 | 用户反馈不做 embedding；prompt 注入索引而非全文 |
| **D-9** | **kb_admin 独立角色** | **v2.0**（本版） | IP 律师 / 资深专代要能维护内部范本，但不应有 admin 监控权限 |
| **D-10** | **本系统文档只读根** | **v2.0**（本版） | admin 调试 / 复盘 / 答疑场景频繁要查 PRD/HLD/runbook，文件树直接看比开终端方便 |

### 13.2 开放问题（TODO）

| ID | 问题 | 当前状态 | 计划版本 |
| --- | --- | --- | --- |
| O-1 | Sentry 接入 + DSN 配置 | 未做 | v0.37 |
| O-2 | sqlite cron 备份脚本 | runbook 有 cmd 未落 | v0.37 |
| O-3 | CAS server 真员工联调 | u1/u2 fixture | v0.37 |
| O-4 | 多租户隔离 cache 穿透 | 未做 | v0.40+ |
| O-5 | 4 节 smart 默认 ON 阈值 | prior_art ON，其余 OFF | v0.38（数据足够后） |
| O-6 | docx 模板让 kb_admin 自定义 | 硬编码 5 章 | v0.38 |
| O-7 | 移动端 a11y 真机扫 | tokens 已就位 | v0.39 |
| O-8 | benchmark 真跑 prod 性能基线 | dry-run 框架 | v0.37 起采样 |
| O-9 | 多 agent 合议的 UI 设计 | 未设计 | v0.40 |
| O-10 | EN disclosure 模板细节 | persona 已支持 US 实务 | v0.40 |

---

## 附录 A：术语表

| 术语 | 释义 |
| --- | --- |
| **报门** | 员工首次描述发明点，对应数据库 `Project` 创建 |
| **interview-first** | 「先问后写」机制：AI 必须问清楚到自评素材足够才能开始写 |
| **mineFull** | 5 章并行写作（prior_art / summary / embodiments / claims / drawings_description） |
| **kb** | 419 篇 CN 专利专家知识库（`refs/专利专家知识库/`） |
| **AgentRunLog** | 每次 agent 调用的入库记录 |
| **fallback** | agent 失败兜底到 mining.py legacy 占位 |
| **detached run** | SSE 后端任务脱离前端连接独立跑，前端可断线重连 |
| **资深代理人 persona** | prompt 注入「CN+US 双轨执业 10 年代理人」人设 |
| **信号** | AI 在文本里输出 `[READY_FOR_WRITE]` 等标记，触发后端状态跃迁 |

---

> 本 PRD 与 [`hld.md`](./hld.md) 配套：PRD 讲「做什么 / 给谁 / 为什么 / 衡量什么 / 不做什么」，HLD 讲「怎么搭 / 模块切分 / 接口长啥样 / 数据怎么走」。如 PRD 与 HLD 冲突，以 PRD 为准。
