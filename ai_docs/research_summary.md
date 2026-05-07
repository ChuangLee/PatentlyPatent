# 调研总览（2026-05-07）

四路并行调研已完成，详见同目录 `research_01_llm_tools.md` / `research_02_data_sources.md` / `research_03_cn_practice.md` / `research_04_skills_architecture.md`。

## 关键结论

### 现状（2025-2026）
1. **开源最佳实践**：AutoPatent（多 agent + PGTree + RRAG）是唯一可学的开源 patent 全文撰写框架，应 clone 作为参考。
2. **检索基线**：PaECTER / PatentSBERTa（英文向量），中文需基于 Qwen3-Embedding 自建"PaECTER-zh"（CNIPA 摘要+引用对微调）。
3. **数据源最优组合**（CN 优先）：
   - 权威：CNIPA 公布公告 + PSS-System（爬虫）
   - 国际同族：EPO OPS（免费 4GB/周）+ USPTO ODP（免费）
   - 语义检索：Google Patents BigQuery `embedding_v1`（免费 1TB/月）
   - 商业增强：incoPat / PatSnap（按预算）
4. **CNIPA 实务核心抓手**：A22.3 三步法 / A26.3 充分公开 / A26.4 支持 / A33 修改超范围 / R20.2 必要技术特征 / 单一性。**2023 指南**强化"事后诸葛亮"禁止与公知常识举证。
5. **Skills 架构**：Progressive Disclosure（主 skill 加载 frontmatter，子 skill 懒加载）+ 文档式 Router。description 必须动词开头 + 含触发关键词。

### LLM 自动化优先级（来自实务调研）
| ROI | 任务 |
|---|---|
| 高 | 检索式生成、特征对照表、OA 三步法草稿、A33 原文锚定校验、附图标号一致性、说明书五段骨架 |
| 中 | 交底问题树、从权梯度、portfolio 草图 |
| 必须人审 | 独权概括度终判、最接近现有技术 D1 重定义、A33/A26.4 边界、商业 portfolio 决策 |

## 第一性原理判断

> 现有商业系统（智慧芽 Eureka、incoPat AI）做了"全流程一键生成"的样子，但实际上把 LLM 当模板填充器，缺三件事：
> 1. **法条嵌入式推理**——不是检索完了交给 LLM 写，而是每一步都让 LLM 基于 A22/A26/A33 的判断逻辑做选择
> 2. **可验证可锚定**——claim 中每个特征必须能锚回说明书原文（A26.3）和原始申请（A33），可机械校验
> 3. **专家心智复刻**——把"上位词的胆量"、"D1 重定义"、"必要技术特征最小集"这种判断显式化为可执行的 prompt + 规则

我们的 skill 系统应在这三点上做差异化。

## 拟设计 skill 列表（草案，待 docs/skill_architecture.md 终稿）

主控 1 个：
- `patent-king` — 主控/路由/全流程编排

子 skill 7 个：
1. `patent-search` — 现有技术检索（要素拆解→检索式→多源召回→特征对照表）
2. `patent-mining` — 技术挖掘/交底书（问题树→上下位→效果矩阵→规避→portfolio）
3. `patent-drafting-claims` — 权利要求撰写（独权概括度+从权梯度+引用关系+R20.2 校验）
4. `patent-drafting-spec` — 说明书撰写（五段骨架+实施例参数表+附图一致性+A26.3 充分性自检）
5. `patent-oa-response` — OA 答辩（三步法重定义+特征对齐+A33 锚定校验+话术）
6. `patent-validity` — 质量/可专利性自审（A22/A26/A33/R20.2 体检报告）
7. `patent-data` — 数据源访问层（CNIPA 爬取+EPO OPS+USPTO ODP+BigQuery+向量化）

## 下一步
1. 在 `docs/skill_architecture.md` 用 mermaid 画主控-子 skill 编排图与数据流
2. 在 `docs/requirements.md` 写可验收需求（输入/输出/边界/人审点）
3. clone 3rd_repos：AutoPatent / Awesome-LLM4Patents / hupd
4. 在 `skills/` 下生成 SKILL.md 骨架
