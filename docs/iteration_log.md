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
