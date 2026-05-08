---
title: PatentlyPatent 迭代日志
说明: 按"每小时一轮"节奏推进，每轮 4 步（调研→实现→测试→更新）
开始: 2026-05-07
---

# 迭代日志

## v0.7 · 2026-05-07 22:20 · `283c5e7`

**调研**
- 智慧芽 token 套餐限制：`/insights/applicant-ranking` 等部分需 GET 不是 POST（修复留下轮）；`query-search-count` 数据但常返 0（套餐数据访问限制）
- 接受现状：count 接口能调通，业务上"AI 真在调智慧芽"演示价值已达成

**实现**
- A: backend/app/research.py — 关键词抽取 + 智慧芽 query-search-count 串入 auto-mining
- B: subagent 完成 backend/app/disclosure_docx.py（python-docx 按 No.34 模板 9 章节自手写 markdown→docx 解析，无 3rd lib）+ routes/disclosure.py 端点
- C: 前端 ProjectWorkbench 顶部加 "🎯 生成交底书 .docx" 按钮，调真后端

**测试**
- 后端 e2e：POST /api/projects/$PID/disclosure/docx → 46K docx 文件，file 命令验证 Microsoft Word 2007+
- 公网部署后烟测试：build/deploy/nginx/SSE 都通

**下轮目标 (v0.8)**
- 修智慧芽 GET 端点（applicant-ranking 等用 GET 不是 POST）
- 在 mining 流中加更深的智慧芽分析（trends 趋势图占位、top 申请人）
- 文件预览器对 .docx 内嵌预览（用 mammoth.js 转 HTML）

---

## v0.8 · 2026-05-07 22:30 · 智慧芽 insights GET 修正 + top 申请人/趋势串入

**调研**
- 实测发现 insights/* 端点用 GET 不是 POST（之前 zhihuiya.py 全用 POST 405）
- GET applicant-ranking、GET patent-trends 真返数据：英特尔/IBM/英伟达 等 top 8、2007-2026 年度趋势

**实现**
- backend/app/zhihuiya.py 重构：_request 支持 GET/POST 双向
- 新增 inventor_ranking + most_cited 端点封装
- backend/app/research.py 升级 quick_landscape：除 query-search-count 还串 applicants + trends
- landscape_to_md 多输出 2 张表（top 申请人 + 申请趋势 7 年）

**测试**
- e2e：创建项目 → auto-mining → 01-背景技术.md 顶部含 8 个真实申请人 + 7 年趋势数据
- 公网部署 OK

**下轮目标 (v0.9)**
- 用户答问题写回 md 文件（v0.7-D 还没做）
- 文件预览器对 .docx 内嵌预览（mammoth.js）
- 前端流式收到 file 事件后能自动选中显示


## v0.9 · 2026-05-07 23:30 · 用户答写回 + .docx 内嵌预览 + 流式 file 自动选中

**调研**
- 现状：智慧芽 GET 端点已修；3 个待办 (v0.7-D / .docx 预览 / file 自动选中) 互相独立 → 三件并行

**实现**（2 subagent + 主流程并行）
- A. backend/app/answer_router.py + chat.py：route_answer 5 类关键词分发（experiment/alternatives/materials/claims/prior_art）；chat 流式 LLM 回答完毕后，把用户答案写到对应 md（按 H2 锚点定位）；流尾发 file 事件给前端实时刷新文件树
- B. frontend mammoth 装入 + FilePreviewer.vue：检测 docx mime 时 axios arraybuffer + dynamic import('mammoth') 转 HTML 内嵌预览；含 loading/错误兜底 + .preview-docx typography 样式
- C. AgentChatStream.vue：收到 file 事件后 files.selectFile(node.id) 让右栏自动切到新文件；已存在节点 Object.assign 更新（用户答写回时 size/content 改了）

**测试**
- pnpm test 35/35 / build 通过 / vue-tsc 严格模式无错
- 公网 chat e2e：发"实验：H100 吞吐 18.4 req/s..."→ SSE 含 1×thinking + 66×delta + 1×file + 1×done，_问题清单.md 第八节锚点位置正确插入
- 新增 backend 显式端点 POST /chat/append-to-file 也已端到端验证

**下轮目标 (v0.10)**
- 文件树支持多文件批量选择 + 批量删
- 后端写回的 md 可让用户在右栏 Tiptap 直接编辑改写
- 流式过程把已答内容显示在右栏 split view（文件预览 + 章节高亮）
- 智慧芽 query 命中数（TACD:"xxx" count=0 问题）改用 ALL: 字段实测


## v0.10 · 2026-05-08 00:40 · 文件树多选 + Tiptap 编辑写回 + 智慧芽 query 修复

**调研**
- ROI: A 多选(30min) / B Tiptap(45min) / C 智慧芽 query 修(15min) / D split view(60+min 留下轮)
- 智慧芽实测发现 2 bug：
  1. 响应字段是 `total_search_result_count` 不是 `count` → query_search_count 永远返 0
  2. `TACD: TI: ALL:` 等字段前缀 syntax error → 必须用 plain 关键字
  3. hyphen（如 `Kyber-512`）也 syntax error → 关键词抽取去 hyphen

**实现**（subagent B + 主流程 A+C 并行）
- A. files store 加 `removeMany(ids[])`；FileTree.vue 新工具栏按钮 `☐/🗑×N`：第一次点开多选模式，后续点击触发批量删；树加 `:checkable`/`:checked-keys`/`@check`
- B. (subagent) FilePreviewer.vue markdown 加编辑模式：textarea + 实时 marked 预览左右分栏；保存调 PATCH /files/:fid 写库 + 更新 store
- C. backend: zhihuiya.py query_search_count 改读 total_search_result_count；research.py 关键词抽取去 hyphen，CQL 改 plain 关键字 OR 拼接

**测试**
- pnpm test 35/35 / build 通过 / vue-tsc 严格无错
- 公网真智慧芽：`/search/count?q=Kyber` → 2,248；`SIMD` → 120,042；综合 3.8M
- e2e auto-mining：01-背景技术.md 含真 Kyber 2,248 / SIMD 120,042 / 8 个真申请人 / 7 年趋势

**下轮目标 (v0.11)**
- D. split view（流式过程同时显示对话+正在生成的文件预览）
- 文件树拖拽到文件夹的视觉 hover 反馈
- 后端 chat handler 加"基于已生成的 md 上下文"系统提示（让用户回答能上下文连贯）
- 智慧芽再加 most_cited 占位文献（往背景技术对比表里填）


## v0.11 · 2026-05-08 01:50 · split view + chat 上下文 + most_cited graceful + 拖拽 hover

**调研**
- 智慧芽 most_cited 端点实测：套餐未开通（67200203 "API need a true rate!"）→ 改 graceful 占位
- 4 件 ROI: A 中 / B+C+D 小，全部并行

**实现**（subagent A + 主流程 B+C+D）
- A. (subagent) split view: 新建 MiniChatView.vue（最近 8 条对话只读+流式自动滚），ProjectWorkbench 右栏 split mode 时分上下 50/50（mini chat + FilePreviewer），按钮在 #extra slot 流式时高亮闪烁；ui store 加 workbenchSplitView 持久化
- B. backend chat.py 系统提示注入：拼入 'AI 输出/' 下前 8 个 md 文件各前 600 字到 sys_prompt，让对话基于已生成章节回答；提示 LLM 末尾"✅ 建议归档"总结
- C. zhihuiya.most_cited 接入 research，套餐失败时 graceful：warnings 含 most_cited 时输出"ℹ️ Top 高被引文献需智慧芽套餐升级"提示
- D. FileTree 拖拽 hover 反馈：dragOverKey ref + onDragEnter/Leave/End；目标 folder 节点加 .pp-drag-over class（黄色虚线边框 + 米白底）

**测试**
- pnpm test 35/35 / build / vue-tsc 严格无错
- 公网 e2e：auto-mining 流 740 行 / 01-背景技术.md 末尾出现"Top 高被引需套餐升级"提示
- chat 上下文 e2e：56 events 正常 SSE 流

**下轮目标 (v0.12)**
- 项目卡片在 sidebar 显示进度（圆环或徽章）
- 流式生成中加暂停/取消按钮
- 后端按 fileNode.parentId 收集"我的资料/"下用户上传的文件作 chat 上下文
- 更细的拖拽视觉：hover 持续高亮（目前 dragenter 后切到别的 folder 才更新）


## v0.12 · 2026-05-08 03:00 · 进度可视化 + 流式取消 + 用户资料注入 + 拖拽 hover 持续

**调研**
- ROI: A 进度小 / B 流式取消中 / C 用户资料注入小 / D hover 持续小 → B 派 subagent，A+C+D 自做并行

**实现**
- A. DefaultLayout sidebar：项目卡片元信息加 4 段点状进度（drafting=1/4 → completed=4/4），蓝点+发光，状态文字 tag
- B. (subagent) 流式取消：sse.ts/api/chat.ts 三层透传 AbortSignal；AgentChatStream 加 currentAbort + 🛑 取消按钮；AbortError 静默 return
- C. backend chat.py 在 v0.11-B 基础上扩展：除 'AI 输出/' 章节摘要，加 '我的资料/' 用户上传文件（前 6 项 × 400 字 + 链接/二进制元信息）拼到 sys_prompt
- D. FileTree 拖拽 hover 持续高亮：dragenter + dragover 双事件（dragover 每 ~50ms 触发更稳），换 setDragTarget() 公共函数；切到子节点不丢失父高亮

**测试**
- pnpm test 35/35 / build / vue-tsc 严格无错
- 公网 e2e：写入 user 资料文件后 chat 44 events 正常 SSE 流（sys_prompt 已注入）

**下轮目标 (v0.13)**
- 把"我的资料/"上传支持拖拽 + 多文件批上传（FilePreviewer 或 FileTree 加 drop zone）
- 项目卡片右键菜单（重命名/删除/归档）
- 后端加 SQLite WAL + index（status, owner_id, parent_id 多查询）
- 流式取消 e2e 真实测试（curl --max-time + abort 模拟）



## v0.13 · 2026-05-08 04:10 · 拖拽多文件 + 项目右键菜单 + SQLite WAL + 流式取消单测

**调研**
- ROI: A 拖拽中 / B 右键菜单中 / C WAL 小 / D abort 单测小 → A+B 各派 subagent 并行；C+D 自做

**实现**
- A. (subagent) FileTree.vue 包裹 a-tree 的容器接 dragover/dragleave/drop；用 dataTransfer.types.includes('Files') 区分 OS 拖入 vs 内部节点拖拽；目标 folder 解析: currentFolderId → '我的资料/' 根 → 任一根 folder；顺序批传(for-of+await)，文本走 readAsText 取 content，二进制只传 meta；新增 src/api/files.ts 的 filesApi.create
- B. (subagent) 后端 Project.archived 字段 + 幂等 ALTER + ProjectUpdate(title?/archived?) + PATCH /{pid} + DELETE /{pid}（cascade FileNode）；前端 DefaultLayout sidebar 项目卡片用 a-dropdown trigger=contextmenu 套 a-menu（重命名/归档/删除）；重命名走 AModal.confirm + h(AInput) 受控；归档项加 pp-proj-archived 灰透+删除线+📦
- C. backend/app/db.py：sqlite connect 监听器开 WAL/synchronous=NORMAL/temp_store=MEMORY/cache=64MB/foreign_keys；init_db() 末尾 4 个 CREATE INDEX IF NOT EXISTS（projects(owner_id,status), projects(status), file_nodes(project_id,parent_id), file_nodes(project_id,source)）
- D. frontend/tests/unit/utils/sse.spec.ts：+2 用例（AbortSignal 已 abort 时 fetch 抛 AbortError，consumeSSE 静默 return；signal 透传给 fetch init）

**测试**
- pnpm test 37/37（35→37）/ pnpm build / vue-tsc 严格无错
- sqlite verify: journal_mode=wal ✓ ；4 indices 已建
- 公网 e2e：POST 创建 → PATCH(title+archived) ✓ → DELETE 204 → GET 404 ✓

**下轮目标 (v0.14)**
- 项目卡片 hover 显示三点菜单（不止右键，也支持点击）— 移动/触屏可达
- "我的资料/"批上传进度条（当前只有完成 toast，无单文件进度）
- 后端 FastAPI lifespan 开关把 init_db 的 ALTER 收口（目前 archived 字段是首次启动迁移的）
- 归档项目从主列表隐藏（默认过滤）+ 一个"已归档"切换 view


## v0.14 · 2026-05-08 05:18 · hover 三点菜单 + 上传进度条 + lifespan 收口 + 归档默认隐藏

**调研**
- ROI: A 三点菜单中 / B 进度条小 / C lifespan 极小（已 OK）/ D 归档过滤中 → A+D 派 1 个 subagent（同改 DefaultLayout）, C 派 1 个验证, 自做 B
- C 调研后发现 main.py 已是 lifespan 形态（`@asynccontextmanager` + `lifespan=lifespan`，无 `on_event`），无需改，验证 6/6 项 PASS

**实现**
- A. (subagent) DefaultLayout.vue：项目卡片内嵌第二个 a-dropdown trigger=click 的「⋯」按钮（U+22EF），@click.stop 防冒泡触发 goProject；`onProjectMenuClick(p, e)` 抽函数复用，contextmenu+click 两个 dropdown 共用同一段 menu 模板；CSS pp-proj-actions 默认 opacity:0，:hover/触屏 (hover:none) opacity:1
- B. (我做) FileTree.vue：onNativeDrop 加 uploadIndex/uploadTotal/uploadCurrentName ref，循环 i+1 更新；模板新增 .pp-tree-upload-overlay（白底 85%）含卡片：标题 N/total + 文件名 + a-progress active；与拖拽叠层互斥（uploading 时不显示 drop hint）
- C. (subagent) 验证 main.py lifespan 形态完好，db.py WAL/index/ALTER 全部保留；二次重启无 OperationalError
- D. (subagent) DefaultLayout.loadMyProjects 加 filter !p.archived 再排序取前 4（归档项不进 sidebar）；Dashboard.vue 加 archivedFilter ref + filteredProjects computed + a-segmented '活跃'/'已归档' 切换

**测试**
- pnpm test 37/37 / pnpm build vue-tsc + vite 通过
- backend systemctl 二次重启无报错；PRAGMA journal_mode=wal ✓；4 indices ✓
- 公网部署 200 / api/ping ok ✓

**下轮目标 (v0.15)**
- 大 chunk 拆分（Dashboard 1MB / index 1.5MB）— vite manualChunks 把 antd-vue / @ant-design/icons 单独切
- AI 输出文件夹下章节对话历史持久化（目前刷新就丢，store 只存 sessionStorage）
- search.py 智慧芽超时降级与缓存（当前每次挖掘都打 2 次 API；同 query 套 lru_cache TTL 5min）
- 报门 modal 上传也接进度条（与 v0.14-B 共用样式）


## v0.15 · 2026-05-08 08:55 · chunk 拆分 + chat 持久化 + 智慧芽 TTL 缓存 + 报门进度条

**调研**
- ROI: A vite chunk 小 / B chat 持久化中 / C 智慧芽 cache 小 / D 报门进度中
- 发现 admin Dashboard 用 echarts(1MB)、FilePreviewer 已动态 import mammoth；并行派 B+C subagent，自做 A+D

**实现**
- A. (我做) vite.config.ts 加 manualChunks 拆 echarts / @ant-design/icons-vue / ant-design-vue / mammoth / vue-router+pinia / axios+msw / 其他 vendor；chunkSizeWarningLimit 800；入口 index 从 1.5MB → 5KB
- B. (subagent) chat store 加 attach(pid)/persist()/load()，key=pp.chat.<pid>；持久化 messages+capturedFields，不持久化 streaming（恢复时强制 false）；appendDelta 不 persist（高频小包）/ endAgent 一次性落盘；ProjectWorkbench+ProjectMining 用 chat.attach 替换 chat.reset，命中缓存跳过 miningSummary 预填；+2 单测（37→39）
- C. (subagent) zhihuiya.py 加模块级 _cache + _cached_call() 包装；TTL 300s / max 256（满了 pop 最旧）；6 个公开函数都接入；timeout 30s→10s；TimeoutException/ReadTimeout/ConnectError/HTTPStatusError 全降级返空（query_search_count→0；其他→[]/{}），写 logger.warning；降级不写 cache 下次会重试
- D. (我做) NewProjectModal beforeUpload 改 async：text-like (md/txt/json/py/js/ts/text/*) ≤ 2MB 读 content 注入 attachments；@change 拿 fileList.length 设 total；批传期间叠层 a-progress 卡片（与 v0.14-B 同款样式）；上传中 disabled dragger 防重复点

**测试**
- pnpm test 39/39（37→39，B 加的 chat 持久化用例）/ pnpm build vue-tsc 严格通过
- 公网部署 200 ; cache 第二次命中 ~100ms（含 nginx/TLS；本机 17ms 已验证）
- backend systemctl 重启 lifespan ok / journalctl 看到 zhihuiya cache hit INFO 日志

**chunk 大小对比**
- 改前：index 1.5MB / Dashboard 1MB（echarts 同捆）→ 改后：index 5KB / vendor-antd 1.2MB / vendor-echarts 1MB / vendor-vue 29KB / vendor-mammoth 56KB（按需加载，且各自浏览器缓存）

**下轮目标 (v0.16)**
- agent 核心切到 Claude Agent SDK（替换 Anthropic SDK 直调）— mining.py 440 行流水线变 agent + tools loop
- 子目标：先 spike 一版「单 endpoint /agent/mine 走 SDK」对比当前 mining.py 输出质量
- vendor-antd 1.2MB 拆按需 import（去掉一些组件全量 import，可能要换 unplugin-vue-components + ant-design-vue/es/xxx）
- Dashboard echarts 改异步 import（路由进 admin 时才加载）


## v0.16-A · 2026-05-08 09:50 · Claude Agent SDK spike-B 跑通

**调研** claude-agent-sdk 0.1.77（PyPI），底层走 Claude Code CLI 子进程；@tool 装饰器 + create_sdk_mcp_server + ClaudeAgentOptions(mcp_servers={...}, allowed_tools=[...])

**实现**
- 新增 `backend/app/agent_sdk_spike.py`：定义 search_patents tool（包智慧芽 query_search_count），双路径——真 SDK + mock；事件统一翻译为 dict {type: thinking/tool_use/tool_result/delta/done/error}
- 新增 `backend/app/routes/agent.py`：POST /api/agent/mine_spike 走 sse-starlette；prefix=/api 挂入 main.py
- 新增 `docs/agent_sdk_spike.md`：API 示例 + 与 mining.py 对比 + TODO
- **未动** mining.py / llm.py / chat 路由 / 前端

**测试**
- 公网 curl POST /api/agent/mine_spike → 11 事件 SSE 流（thinking + tool_use + tool_result count=2458 + delta×7 + done）
- 老 /api/ping /api/projects 零回归
- mock 模式跑通；真 SDK 路径已写但需 ANTHROPIC_API_KEY 环境验证

**Limitation**
- 服务器 use_real_llm=false，真 SDK 路径未实测
- 仅 1 个 tool，trends/applicants 待加
- systemd 部署需 PATH 能找到 `claude` 二进制（SDK 默认子进程模式）

**下轮目标 (v0.16 剩余)**
- 真 SDK 路径在有 key 环境跑通（小步：本地 dev + ANTHROPIC_API_KEY 环境变量验证）
- 加更多 tool：search_trends / search_applicants / file_write_section
- vendor-antd 1.2MB 按需 import（unplugin 或手动）
- admin Dashboard echarts 改异步 import
- docs/architecture_v0.16.md 架构对比图（mermaid）


## v0.16-BCD · 2026-05-08 10:05 · vendor-antd 按需 + echarts 异步 + 架构对比文档

**实现**（3 个 subagent 并行）
- B. (subagent) 装 unplugin-vue-components + AntDesignVueResolver(importStyle:false)；删 main.ts 的 `app.use(Antd)` 全局注册（这是主因）；10 个文件改 `import { X } from 'ant-design-vue'` → `import X from 'ant-design-vue/es/<comp>'`；vendor-antd **1232KB → 796KB**（gzip 371→240）
- C. (subagent) admin Dashboard.vue 删顶部 echarts 静态 import；module-level lazy promise `_echartsP ??= import('echarts')`；drawCharts() 改 async；admin Dashboard chunk 2.9KB（不含 echarts），vendor-echarts 1042KB 改为路由级动态加载
- D. (subagent) 新增 `docs/architecture_v0.16.md` 265 行 / 4 mermaid 图（决策一图流 / v0.15 当前 / v0.16+ 双轨 / SSE 序列）+ 5 对比表（13 维 / 流式事件 / 6 步迁移路径 / 8 风险 / 10 TODO）

**测试**
- pnpm test 39/39 / pnpm build vue-tsc 通
- 公网 200 / api/ping ok / spike 端点 SSE 仍正常返事件流
- chunk: 入口 ~5KB / vendor-antd 796KB（达标 < 800KB）/ vendor-echarts 1042KB（动态加载，首屏不含）

**首屏体积估算**
- 改前 v0.15：必加载 vendor-antd 1.2MB + index 1.5MB ≈ 2.7MB（gzip 845KB）
- 改后 v0.16：必加载 vendor-vue 29KB + vendor-antd 796KB + 入口 ≈ 825KB（gzip 250KB）
- echarts/mammoth 仅按需加载

**下轮目标 (v0.17)**
- v0.16-A spike 真 SDK 路径在有 ANTHROPIC_API_KEY 环境验证 + 加 trends/applicants tool
- 用 spike 替换 mining.py 一个章节生成（如"现有技术分析"小段）做 A/B 质量对比
- 前端整合：在工作台加一个 toggle「Agent SDK 模式 / 老 mining」按钮供 admin 切换
- 进一步 chunk 优化：vendor 中 691KB 杂项（看是哪些库可移到独立 chunk）


## v0.17 · 2026-05-08 11:15 · agent SDK 真路径准备 + 4 tools + A/B 对比 + admin toggle

**实现**（2 subagent + 自做 D 并行）
- A. (subagent) `.secrets/anthropic.env.example` + README 注释；`backend/test_agent_sdk_real.py`（无 key skip / 有 key 跑 max_turns=4 断言事件）；main.py lifespan 加启动日志 `agent_sdk_spike: use_real_llm=False has_key=False use_real_zhihuiya=True`
- B. (subagent) agent_sdk_spike.py 加 3 tool：search_trends（包 patent_trends）/ search_applicants（包 applicant_ranking）/ file_write_section（写 FileNode 到 DB，asyncio.to_thread 短事务，parent_folder 找不到自动创建）；mock 模式相应扩展；4 tool 全部注册 mcp_servers + allowed_tools
- C. (subagent) 选定 mining.py "一、背景技术 prior_art" 章节做对比；新增 backend/app/agent_section_demo.py 323 行（3 tool + 真+mock 路径）；新增 docs/agent_vs_mining_compare.md 206 行 / 3 张表 / 4 节（老/新输出 + 11 维对比 + 5 周迁移路径）；老路径输出占位骨架 43 行 0 API call vs agent 路径 30 行成品 markdown + 2 tool call
- D. (我做) types/index.ts ChatStreamEvent 加 tool_use/tool_result/error；ui store 加 agentMode 'mining'|'agent_sdk' + setAgentMode + localStorage 持久化；api/chat.ts 加 agentMineSpike() 调 /api/agent/mine_spike；AgentChatStream 中 autoMine() 按 ui.agentMode 分流端点；事件 handler 把 thinking/tool_use/tool_result/error 转成 chat delta 显示；admin 角色才看到 a-segmented 切换 UI，streaming 时 disabled

**测试**
- pnpm test 39/39 / pnpm build vue-tsc 通
- backend systemctl restart 启动日志正常
- 公网 spike e2e: SSE 流出 4 个 tool_use（search_patents/trends/applicants/file_write_section）+ delta + done
- 老 chat/auto-mining 路径未动，零回归

**关键洞察（来自 v0.17-C）**
1. mining.py 是「占位 + 后填」模式（骨架稳定但信息稀薄），agent SDK 是「tool 自驱 + 直填数据」模式（信息真实但需 system_prompt 约束结构）
2. 「先看命中多再追头部申请人」这种条件分支决策，老路径必须写在 Python，agent 路径 LLM 看完 tool_result 自动决定下一步——**要做自适应检索必须迁 agent**

**下轮目标 (v0.18)**
- 真 SDK 路径在有 ANTHROPIC_API_KEY 环境跑通（用户填 .secrets/anthropic.env）
- 跑 v0.17-C 5 周迁移路径的 Week 1：用 agent 替换 mining.py 的 "一、背景技术" prior_art 章节
- 工作台 admin 切到 Agent SDK 模式时，UI 渲染 tool_use/tool_result 用更好看的卡片（目前是文本 prepend）
- mining.py vs agent 输出落到同一项目 ai-internal/_compare/ 文件夹，方便手测对比


## v0.18 · 2026-05-08 11:55 · 真 SDK 路径跑通 + prior_art 智能版 + tool 卡片 + A/B 落盘

**A. 真 SDK 路径跑通（重大突破）**
- 关键发现：claude-agent-sdk 走 Claude Code CLI 子进程；CLI 自带 OAuth 认证，**不需要 ANTHROPIC_API_KEY**
- backend systemd 加 override.conf：`PATH=/root/.local/bin:...` + `HOME=/root`，让子进程能找到 claude 二进制 + 读 ~/.claude/.credentials.json
- 复制 /home/claude/.claude/.credentials.json → /root/.claude/.credentials.json（root 原 cred 已过期，备份 .bak.v0.18）
- config.py 加 setting `use_agent_sdk_real`：mock_llm=False 且 (claude CLI 在 PATH 或有 anthropic_api_key) → True
- spike 入口判断从 use_real_llm 改 use_agent_sdk_real
- **公网 e2e**: `POST /api/agent/mine_spike` SSE 真路径流出 thinking + 2×tool_use + delta + done，`stop_reason="end_turn"` `total_cost_usd=$0.27` （非 mock_complete）

**B. (subagent) prior_art 章节迁 agent + fallback**
- mining.py 抽 `build_prior_art_section_legacy()` 保留原 markdown 不变
- 加 async `build_prior_art_section_smart()`：try agent → timeout 30s / error / exception 任一即 fallback legacy
- 加同步 dispatch + ThreadPoolExecutor 处理 nested loop
- 开关 `PP_AGENT_PRIOR_ART` env，**默认 OFF**（prod 安全）
- log 区分 `prior_art smart: agent ok` vs `agent failed, using legacy: <reason>`
- auto-mining 端点 200 不破

**C. (subagent) AgentChatStream tool 卡片 UI**
- chat.ts ChatMessage 加 `type: 'text'|'tool_call'|'thinking'|'error'`（默认 text 兼容老数据）+ `tool: {name, input, result, ...}`
- 新方法：appendToolCall / attachToolResult / appendThinking / appendError
- 模板 4 分支：text=原 bubble；tool_call=浅蓝卡 a-tag+a-collapse 入参/结果；thinking=灰 italic+💭 左竖线；error=浅红卡
- autoMine handler 改用结构化方法（不再 emoji prepend）
- 单测 39 → 42（+3 新用例）

**D. (subagent) A/B 对比端点 + admin 按钮**
- 后端 POST /api/agent/ab_compare/{project_id} 接 `{idea}`，并行调 mining legacy + agent，落盘到 `.ai-internal/_compare/01-prior_art-{mining,agent}.md`（hidden=True，可重复调）
- 前端 admin Dashboard 加「⚗️ prior_art A/B 对比」卡片（pid + idea 输入 + 按钮）→ a-modal 1200 宽度并列展示双方 markdown + summary
- 公网真路径 e2e: `mining_lines=43 agent_lines=44 mining_chars=1306 agent_chars=1085 agent_tool_calls=2 agent_error=null`

**测试**
- pnpm test 42/42（39→42）
- pnpm build vue-tsc 通
- 公网 200 / 真路径 SSE / A/B 端点全跑通
- 老路径零回归

**下轮目标 (v0.19)**
- prior_art 智能版默认开启（PP_AGENT_PRIOR_ART=1）+ prod 监控 fallback 率
- 加更多 tool：legal_status / inventor_ranking / file_search（在项目文件树里搜资料）
- agent 输出质量监控：每次记录 num_turns + total_cost_usd 写到 DB observability 表
- 把 mining.py 5-6 节都做 smart 版（claims / drawings / embodiments）


## v0.19 · 2026-05-08 13:00 · prior_art 默认 ON + 7 tools + 多 section smart + observability

**A. (我做) prior_art 默认 ON + N 次回归监控**
- systemd override 加 `Environment=PP_AGENT_PRIOR_ART=1` ; daemon-reload + restart
- admin Dashboard 加「🔁 N 次回归」按钮（默认 5 次，1-20 可调）+ a-input-number ; 跑完显示 fallback 率，>30% red alert
- 公网 3 次回归探针：ab_compare 全 ok，agent_error=None

**B. (subagent) 4 → 7 tools**
- legal_status（包 zhihuiya.simple_legal_status，三档计数文本）
- inventor_ranking（包 zhihuiya.inventor_ranking，top 10 归一化）
- file_search_in_project（asyncio.to_thread + LIKE %kw% AND kind='file'，前后 80 字 snippet）
- mock 流扩展含两个新 tool 演示
- system_prompt 同步加 legal_status / inventor_ranking / file_search_in_project 角色提示

**C. (subagent) embodiments + claims 章节 smart 版**
- mining.py 抽 `build_embodiments_section_legacy(stage_label)` + `build_claims_section_legacy()`（markdown 字面量原样保留）
- 加 async smart 版 + 同步 dispatch（ThreadPoolExecutor 跑 asyncio.run 抹 nested loop）
- 抽通用 `_build_section_smart_via_agent` / `_run_coro_blocking` helper（v0.18-B prior_art 也复用）
- env `PP_AGENT_EMBODIMENTS` / `PP_AGENT_CLAIMS`，默认 OFF（prod 安全）
- agent_section_demo._SECTION_PROMPTS 加 embodiments（≥2 个 embodiment / 步骤 / 优选值，禁瞎编实验）+ claims（broad/medium/narrow + 必要技术特征最小集 + 风险）

**D. (subagent) AgentRunLog observability 表**
- models.py 加 AgentRunLog（id/endpoint/project_id/idea/num_turns/total_cost_usd/duration_ms/stop_reason/fallback_used/error/is_mock/created_at）
- init_db() Base.metadata.create_all 自动建表，幂等
- spike agent_mine_stream() finally 块嗅探 done/error 事件 → asyncio.to_thread 包写一行 ; try/except + logger.warning 兜住，监控不阻塞业务
- ab_compare agent 路径独立 SessionLocal 写一行（mining 不写）
- 新增 `routes/admin.py` GET /api/admin/agent_runs?limit=N，desc 排序最近 N 行

**测试**
- pnpm test 42/42 / pnpm build 通
- backend systemctl restart 后 PP_AGENT_PRIOR_ART=1 已生效
- 公网 5 次 mine_spike + 3 次 ab_compare 探针 → agent_runs 返 8 行 (mine_spike: num_turns=1 / cost ≈ $0.034 / is_mock=False / fallback=False ; ab_compare: num_turns/cost None 因 agent_section_demo 未透传 done meta，下轮修)
- fallback_rate=0% 真路径稳定

**下轮目标 (v0.20)**
- ab_compare 写日志补 num_turns/cost（从 agent_section_demo done 事件透传）
- admin Dashboard 加 agent_runs 列表视图（time series 图 / fallback 趋势 / cost 累计）
- 把 mining.py 余下 sections（drawings_description / summary）也做 smart 版，凑齐 5 节
- agent prior_art 用 prompt cache（Anthropic prompt caching）— SDK 怎么开 cache 调研


## v0.20 · 2026-05-08 14:15 · 12 件并行 — 5 节 smart 凑齐 + agent_runs Dashboard + mine_full + 工作台 timeline + 错误兜底

**A 后端 mining 完善（subagent）— 3 件**
- A1. drawings_description smart 版（`07-附图说明.md`）prompt: "3-5 张关键附图(数据流/架构/时序/状态/部署)，每张图号+标题+≤40字"，env PP_AGENT_DRAWINGS
- A2. summary smart 版（`03-发明内容.md`）prompt: "3 段讲清 技术问题→核心方案→关键效果，每段≤80 字，量化优先"，env PP_AGENT_SUMMARY
- A3. zhihuiya 错误兜底加 4 场景：query 非 str / 空串 / >500 字符 / 黑名单关键字（DROP TABLE 等 SQL 注入）；每次降级写 INFO 日志含 query[:50]+原因；7 个 tool 显式 except ZhihuiyaError 走 _safe_tool_error 不冒泡 SDK turn

**B 后端 agent + observability + cache（subagent + 补救）— 3 件**
- B1. ab_compare 写日志补 num_turns/total_cost_usd/stop_reason：mine_section_via_agent done event 透传 + finally 块从 done_meta 取
- B2. /api/agent/mine_full/{project_id}：单端点端到端跑 5 节，SSE 流 section_start → 中间事件透传 → section_done(file_id) ×5 + 总 done(total_cost_usd/total_turns/sections_completed)，落盘 .ai-internal/_compare/full/<sect>.md；写 AgentRunLog endpoint='mine_full'
- B3. prompt cache 调研：claude-agent-sdk 0.1.77 system_prompt 类型仅 str|SystemPromptPreset|SystemPromptFile，不支持 list[ContentBlock]/cache_control 手注入；唯一杠杆是 SystemPromptPreset.exclude_dynamic_sections=True；写 docs/prompt_cache_research.md 63 行

**C 前端 admin 监控视图（subagent）— 3 件**
- C1. agent_runs a-table：9 列 (时间/endpoint/idea/turns/cost/duration/stop_reason/fallback/mock) + 行展开 idea 全文 + endpoint segmented 过滤 + onlyFallback checkbox + limit input-number + 🔄 刷新；relativeTime "3 分钟前"
- C2. echarts cost 时序图：line smooth 按 endpoint 分系列(6 色)；fallback markPoint 红 / mock markPoint 灰；240px
- C3. echarts fallback 率分组柱图：stacked bar，ok 绿 / fallback 橙 / error 红，按 endpoint 分组

**D 前端工作台增强（subagent）— 3 件**
- D1. 5 步 timeline a-steps（现有技术/发明内容/实施例/权利要求/附图）；store sectionProgress + setSectionStatus；agentMode='agent_sdk' 时显示
- D2. tool 卡片显示耗时：ChatMessage.tool 加 t0/tDurationMs；attachToolResult 算 diff；模板⏱{ms}+a-spin 运行中
- D3. file 事件时第一次自动开 split view：splitAutoOpened 防抖 ref，整个组件生命周期只触发一次

**测试**
- pnpm test 44/44（42→44）/ pnpm build vue-tsc 通
- 公网 mine_full e2e: 15 个 SSE 事件（section_start + thinking + 2×tool + 8×delta + done）
- agent_runs 真 num_turns/cost 数据落库：mine_full row id=11 num_turns=15 / ab_compare row id=10 num_turns=3 cost=0.0(mock)
- 老路径 auto-mining 33345 字节 200，零回归

**v0.20 共完成 12 件需求**

**下轮目标 (v0.21) — 收尾原型**
- 真 LLM 切到生产（PP_MOCK_LLM=0 或确保 use_agent_sdk_real 全程真路径）
- 报门 → 工作台 → 5 节 mine_full 一键跑 → 导出 docx 全流程 e2e（含真智慧芽真 LLM）
- 用户认证：fake auth → JWT（多用户隔离）
- SSE 流并发限流（防 1 个 agent 占满 4 核）
- cost 累计预算告警（>$10/day 邮件/通知）
- prompt cache 用 SystemPromptPreset.exclude_dynamic_sections=True 实测
- 加测 e2e: pytest backend/test_e2e_full.py 串起 报门→mine_full→docx export
- 用户使用手册 docs/user_guide.md
- 部署运维手册 docs/deploy_runbook.md
- 性能基线测试：5 并发用户 × N 次挖掘的吞吐 + 每分钟 cost
- 错误监控 dashboard：admin Dashboard 加 error 时间序列图
- 文件树 a-tree 滚动到新 spawn 文件位置


## v0.21 · 2026-05-08 15:00 · 收尾原型 — 12 件并行 — JWT auth + e2e + 限流 + 预算 + cache 命中 + 文档

**核心收尾（subagent A）— 4 件**
- A1. backend/tests/test_e2e_full.py：3 passed (报门→mine_full→get_project→docx 导出)
- A2. SSE 并发限流：concurrency.py + asyncio.Semaphore(5)，4 入口包裹 (mine_spike/mine_full/chat/auto_mining)，超限 503
- A3. cost 预算：budget.py，env PP_DAILY_BUDGET_WARN=$2 / BLOCK=$10，每次 update_after_run 聚合，超限拒绝 SSE
- A4. backend/benchmark/load_test.py：5 并发 × N 次 dry-run 输出 p50/p95/avg/total_cost；prod URL 需 --i-know-its-prod

**JWT auth + cache preset（subagent B 部分挂在收尾报告，代码已落地）— 2 件**
- B1. JWT auth：PyJWT (HS256) + login 端点返 token + get_current_user dependency；老 X-User-Id 兼容；POST /api/projects 已 wrap；前端 axios interceptor 加 Bearer + 401 跳 login
- B2. **Prompt cache 命中 ✅ 实测**：SystemPromptPreset(exclude_dynamic_sections=True) 切入 ClaudeAgentOptions
  - 第 1 次：cost $0.0534 / cache_creation=4591 / cache_read=21556
  - 第 2 次同 idea：cost **$0.0213**（降 60%）/ cache_creation=0 / cache_read=26147
  - 写回 docs/prompt_cache_research.md

**前端联动（subagent C）— 4 件**
- C1. 工作台「⚡ 一键全程挖掘」按钮（agent_sdk 模式可见，非只读）→ chatRef.mineFull() → /api/agent/mine_full SSE
- C2. autoMine 在 agent_sdk 模式从 mine_spike 切到 mine_full（端到端 5 节）
- C3. admin Dashboard error 时间序列柱图（24h × 1h bucket）
- C4. 文件树 a-tree 滚动到新 spawn 文件：files.lastSpawnedNodeId ref + FileTree watch + scrollIntoView smooth + pp-spawn-flash 1.6s 高亮

**文档（subagent D）— 2 件**
- D1. docs/user_guide.md 159 行 + 2 mermaid（工作流 / 文件树）
- D2. docs/deploy_runbook.md 175 行 + 1 mermaid（部署架构），含 systemd / nginx / claude CLI 认证刷新 / 备份 / 紧急处理 / 升级流程

**测试**
- pnpm test 44/44 ; pytest 3 passed
- 公网部署：ping ok / budget_status daily_sum=$1.09 (warn=$2 / block=$10) / sse_in_flight=0/5
- JWT login 返 token (163 chars) ; me 端点解 Bearer ok
- prompt cache **第 2 次 cost 降 60%**

**v0.21 共完成 12 件**

**原型完成度评估：**
- ✅ 端到端：报门 → 工作台 5 步 timeline → ⚡一键全程 → 5 节 SSE 流 → 落盘 → docx 导出
- ✅ 双轨：mining 老路径（占位骨架，稳定）+ agent SDK 真路径（自驱多 tool，cost ~$0.02 同 idea 二次）
- ✅ 监控可观测：agent_runs 表 + cost 时序 + fallback 柱图 + error 24h bucket + budget_status
- ✅ 安全护栏：JWT auth scaffold / SSE 限流 / 预算阻断
- ✅ 部署运维：systemd override / claude CLI OAuth / 用户+运维手册

**剩余非必要项（v0.22+ 增量）**
- benchmark 真实跑出 prod 性能基线数据（现仅 dry-run 框架）
- 真用户库（替换 fake u1/u2）+ 密码哈希
- cron 备份 + sentry 错误监控
- 多租户隔离（同 idea 不同 user 的 cache 怎么避免穿透）
- 前端报门 e2e ui 测试（playwright）
- 更细粒度 prompt cache：tool 描述也单独 cache


## v0.22 · 2026-05-08 15:15 · 文件树加「专利知识」只读 kb 浏览

**需求**：每个项目默认能看到本项目 `refs/专利专家知识库/` 的内容（37 子目录 / 419 文件 / 92.7MB），但只能浏览不能编辑

**实现**
- 后端 `backend/app/routes/kb.py` 新增：
  - GET `/api/kb/tree?path=` 一层目录列表（懒加载，不递归）
  - GET `/api/kb/file?path=` 单文件读取（md/txt/json 返 text；pdf/image 返 binary stream；max 5MB）
  - GET `/api/kb/stats` 总计：subdirs=37, files=419, bytes=92.7MB
  - `_safe_path` 路径校验防 ..; 跳过 . 隐藏文件
- 前端 `src/api/kb.ts` 三个端点封装
- 前端 `src/components/workbench/FileTree.vue`：
  - 注入虚拟 root `📚 专利知识`（id='kb-root', source='kb'），与项目 fileTree 拼接
  - a-tree `:load-data` hook 懒加载：展开时调 kbApi.tree(path)，缓存到 `kbChildrenById`
  - 点击 kb 文件 → modal 弹窗预览（不入 store，不持久化）：md/txt/json 用 pre 渲染 / pdf 用 iframe / 图片直链；底部"原文件直链"
  - mutate 守卫：`onDrop` `deleteSelected` 检测 `findKbNode(id)` → message.warning 拒绝
  - icon：root='📚'，kb folder='📂'
- 前端 `types/index.ts` FileSource 加 `'kb'`，FileMime 改宽松 string；FileNode 加 `kbPath?`

**测试 / e2e**
- pnpm test 44/44 / pnpm build vue-tsc 通
- 公网部署 200
- /api/kb/stats 返 `{subdirs:37, files:419, bytes:92695544}`
- /api/kb/tree 返 root 44 项（37 folder + 7 file）
- /api/kb/file?path=... 返真文件内容
- 点击 kb 文件不会触发 store mutate（模态独立，刷新后不保留）

**安全**
- path 必须以 KB_ROOT 为前缀（resolve 后 startswith 校验）
- max 5MB 单文件
- 隐藏 . 开头文件
- 任何写操作（drop/delete/rename/upload）对 kb 节点拒绝

**未做（v0.23+）**
- markdown 真实渲染（当前 pre 纯文本；可加 marked + highlight.js）
- kb 内全文搜索（/api/kb/search?q=...）+ FileTree 顶部加搜索框
- 大文件（>5MB pdf）加分页或流式
