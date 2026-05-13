# PatentlyPatent 使用手册

> 企业自助 AI 专利挖掘平台。访问 https://blind.pub/patent

## 5 步出交底书

| 步 | 操作 |
|---|---|
| 1 | 登录（账密或 CAS SSO） |
| 2 | 「✨ 新建」填发明描述，可拖入 PDF / PPT / Word / Excel 作为附件 |
| 3 | 附件上传完成后 **AI 自动开始调研挖掘**（智慧芽 + Web + 知识库 + 你上传的资料）；如想推翻重来点 **🔄 重新挖掘** |
| 4 | AI 在聊天里问你 ≤3 个关键事实/数据，**你直接回复** |
| 5 | 信息足够后 AI 自动写 5 节交底书初稿 → 点右上 **🎯 生成交底书 .docx** 导出 |

## 顶部按钮

| 按钮 | 时机 |
|---|---|
| ▶ 开始挖掘 | 自动挖掘没启或被取消时手动启 —— 主按钮，紫色 |
| 🔄 重新挖掘 | 已挖过想推翻重来 —— 清空 plan + 取消旧 run + 重启 interview |
| 🎯 生成交底书 .docx | AI 宣告 `[READY_FOR_DOCX]` 后呼吸高亮可点 |

## 工作台布局

```
左 sidebar：项目列表 + 当前项目文件树（独立滚动）
中：聊天 + 输入框（满高，输入框固定底部）
右：文件预览 Drawer（点文件树自动出，4 态：浮层 50% / 全屏 / 钉固定 / 关闭）
```

## 文件夹

| 文件夹 | 内容 | 权限 |
|---|---|---|
| 📁 **我的资料** | `0-报门.md`（系统自动落地）+ 你上传的文件 | 可读可写 |
| 📁 **AI 输出** | AI 写的 5 节初稿 + `调研下载/` 关键文献摘要 + `专利交底书.docx` | 可读可写 |
| 📖 **本系统文档** | 使用手册 / PRD / HLD / 部署手册 | 只读 |
| 📚 **专利知识** | 419 篇 CN 实务知识库（CNIPA 审查指南 / 复审无效案例 / IPRdaily 等） | 只读 |

## 看 AI 在干啥

聊天里依次出现：
- **📋 当前计划**（顶部 sticky）—— agent 用 `update_plan` 工具维护 6-8 步 TODO，每步状态实时勾选
- **✓ 步骤完成汇报** —— 一步做完 harness 自动推一行绿色气泡（不靠 AI 自觉，工程层保证）
- **🛠️ 调研过程 · N 步**（可折叠）—— 连续 thinking + 工具调用合并成一个分组，点开看每个工具的入参/结果/耗时
- **AI 气泡** —— token 级流式 markdown（含 mermaid 图）

AI 用的工具：
- **A 路 智慧芽托管 MCP**（首选）：`patsnap_search` 关键词/语义检索 / `patsnap_fetch` 拉权要法律同族 / `suggest_keywords` 同义词扩展 / 分类号/申请人/图像/嵌套等共 19 个工具
- **B 路 BigQuery 降级备选**：`bq_search_patents` / `bq_patent_detail`（Google Patents 全量，中文译本，免费；A 路业务错时自动启用）
- in-house 智慧芽 REST 兜底：`search_patents`（命中量）/ `search_trends`（年度趋势）/ `search_applicants`（Top 申请人）/ `inventor_ranking` / `legal_status`
- 通用 Web：`WebSearch` / `WebFetch`（W3C/IETF 标准、同行开源、技术博客）
- 内置 kb：`search_kb` / `read_kb_file`（419 篇 CN 实务）
- 项目文件：`read_user_file`（读 PDF/pptx/docx/xlsx 全文）/ `file_search_in_project` / `save_research`（落关键文献到「AI 输出/调研下载/」）/ `file_write_section`
- 计划：`update_plan`

## 常见问题

| 问题 | 处理 |
|---|---|
| 进项目就"思考中"卡住 | 强刷 + 点 🔄 重新挖掘 |
| 自动挖掘没启动 | 检查附件是否全部上传完（聊天里会有"附件上传完成 N/N"）；如已传完仍未启可手动点 ▶ 开始挖掘 |
| docx 按钮灰着 | AI 还没宣告 ready；等收尾问题答完按钮会呼吸高亮 |
| 智慧芽返回业务错 | A 路余额到期或限流时 AI 会自动切到 B 路 BigQuery；如两路都返空联系运维 |
| AI 长时间没响应 | 60s 自动取消并提示重试；如重复发生联系运维查 CLI 凭证 |
| 想推翻重挖 | 点顶栏 **🔄 重新挖掘** |
| 想删项目 | Dashboard 项目卡右上 ⋯ → 删除；或勾选多个批量删除 |

## 注意

- 不要上传敏感个人/客户数据
- AI 写的 5 节是**初稿**，必须代理人最终审；本系统**不替代**专利代理人的法律判断
- 日预算 $10 上限，超了 503，第二天自动恢复
- 老 `.doc` / `.ppt` 格式不支持，请用户另存为 `.docx` / `.pptx`
