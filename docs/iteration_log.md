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

