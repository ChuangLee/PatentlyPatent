# 调研 2：专利数据库与 API（2025-2026）

## 综合对比

| 数据源 | 覆盖 | 全文 | API/抓取 | 配额/价格 | 推荐度 | 备注 |
|---|---|---|---|---|---|---|
| **CNIPA 公布公告** epub.cnipa.gov.cn | CN 全量公开 | 有 PDF | 无开放 API，需爬 | 免费但反爬强（会话+验证码） | ★★★★ | CN 一手源 |
| **CNIPA PSS-System** | CN+多国 | 全文+法律状态+同族 | 无 API，登录爬 | 免费，限流+动态 token+滑块 | ★★★ | 官方检索分析 |
| **CNIPA 公共服务平台** ggfw.cnipa.gov.cn | CN | bib+法律状态 | 申请制 API | 政府/机构白名单 | ★★ | 普通开发者难拿 |
| **PatSnap 智慧芽 Open Platform** | 170+ 国 1.8 亿+ | 全文+同族+诉讼+法律 | REST API | 商业，无公开免费档 | ★★★★ | 语义+图像检索 |
| **incoPat 开放平台** open.incopat.com | 1.9 亿+/171 国 | 全文+权要+附图+DWPI 中文 | HTTPS POST/JSON | 商业 | ★★★★ | 法律状态/价值度/SEP 字段强 |
| **大为 dwpatent** | 全球 | 全文 | 无成熟开放 API | 商业 | ★★ | 二次开发弱 |
| **USPTO PatentSearch / ODP** data.uspto.gov | US | 全文+claims+citation | REST（2025-05 legacy 停服；2026-03-20 全量迁 ODP） | 免费，需 API key | ★★★★★ | US 最佳免费源 |
| **EPO OPS v3.2** | EP+WO+INPADOC+多国 | 全文+claims+desc+legal+family | REST + SDK | 免费 4 GB/周（非商用） | ★★★★★ | 国际同族/法律状态权威 |
| **Google Patents BigQuery** patents-public-data | 100+ 局含 CN | 全文（多语种译） | SQL on BigQuery | 1 TB/月免费 | ★★★★★ | 自带 `embedding_v1` 64-d 向量 |
| **Lens.org API** | 153M 专利+266M 文献 | 全文 | REST，120+ 字段 | 免费学术试用 | ★★★★ | 专利+论文一体 |
| **PQAI** projectpq.ai | 68 局 1 亿+ | 语义检索 | REST，2025 上 transformer | 开源核 + PQAI+ | ★★★ | 喂段落出 prior art |

## CN 优先 + 全流程检索的数据源组合

**核心栈**：
- **权威落地**：CNIPA 公布公告 + PSS-System（爬虫层处理验证码/限流）
- **商业增强**（预算够）：incoPat API（法律/价值度/SEP）或 PatSnap API（语义+图像）
- **国际同族/法律状态**：EPO OPS（免费 4GB/周）+ USPTO ODP（免费）
- **语义检索/相似专利**：Google Patents BigQuery `embedding_v1`（零成本预训练向量）
- **prior art 初筛**：PQAI
- **论文-专利交叉**：Lens
- **CN 全文兜底**：BigQuery `patents-public-data.patents` CN 译文

## 关键链接
- CNIPA API 说明：https://www.cnipa.gov.cn/jact/front/mailpubdetail.do?transactId=475602&sysid=6
- 公布公告：http://epub.cnipa.gov.cn/
- PSS-System：https://pss-system.cponline.cnipa.gov.cn/
- PatSnap：https://www.zhihuiya.com/api
- incoPat：https://open.incopat.com/
- USPTO ODP 迁移：https://data.uspto.gov/support/transition-guide/patentsview
- EPO OPS：https://patent.dev/epo-ops-v3-2-go-client-library/
- Google Patents：https://github.com/google/patents-public-data
- BigQuery embedding_v1：https://cloud.google.com/blog/products/data-analytics/expanding-your-patent-set-with-ml-and-bigquery
- Lens：https://about.lens.org/lens-apis/
- PQAI：https://projectpq.ai/best-patent-search-apis-2025/
