# 智慧芽 (PatSnap) 开放平台 API 调研 + 实测

> 调研日期：2026-05-07  
> 凭证：`/root/ai-workspace/patent_king/.secrets/zhihuiya.env`（`ZHIHUIYA_TOKEN=sk-***`，长度 51）  
> 文档入口：<https://open.zhihuiya.com/devportal/api-reference/>  
> 实际 API Base：`https://connect.zhihuiya.com`（注意：`.env` 里的 `ZHIHUIYA_API_BASE=https://open.zhihuiya.com` 是文档站，**不是 API 调用地址**）

---

## 1. 是否有 MCP？—— 有，且官方+三方两条路并存

| 来源 | 类型 | 地址 | 状态 |
|---|---|---|---|
| **PatSnap 官方** | Remote MCP（HTTP/SSE） | `https://connect.patsnap.com/1458a4/mcp` | 已上线，需单独申请 MCP Key（与本项目这枚 `sk-` 应用 key **不通用**） |
| **KunihiroS/patsnap-mcp** | npm 本地 stdio MCP | `npx @kunihiros/patsnap-mcp` | 用 PatSnap `client_id+client_secret` 走 OAuth；封装 9 个 insights 工具 |

官方文档：<https://open.patsnap.com/devportal/guides/mcp-overview>  
三方源码：<https://github.com/KunihiroS/patsnap-mcp>（直接读 src 拿到了 endpoint 全清单，见 §3）

**结论**：智慧芽是"REST + MCP 双轨"，但 MCP 走的就是同一批 `/insights/*` REST 端点；patent_king 项目自己封装即可，没必要套一层 MCP。

---

## 2. 认证机制（实测）

- 方式：**Bearer Token**（也接受 `?apikey=` query 参数）
- Key 形态：`sk-` 前缀 + 48 字符（共 51）
- 错误码（实测捕获）：
  - `67200008` — apikey 缺失（无 Authorization 头）
  - `67200202` — apikey 校验失败（host 不对，例如把 zhihuiya 的 key 拿去打 `connect.patsnap.com`）
  - `67200203` — **"API need a true rate!"** 端点未购买/未开通配额（HTTP 仍是 200！业务层判断）
  - `68300004` — 必填参数缺失（如缺 `patent_number`）
  - `10001` — 必填查询串参数缺失（如缺 `lang`）

```bash
# 标准调用模板（实测可用）
curl -sS "https://connect.zhihuiya.com/insights/patent-trends?keywords=lithium%20battery" \
  -H "Authorization: Bearer ${ZHIHUIYA_TOKEN}"
```

**重要**：HTTP 状态码 200 ≠ 业务成功；务必判断 `status:true && error_code:0`，否则 fallback。

---

## 3. 关键端点表（实测分类）

### 3.1 Insights 智能分析（`GET /insights/*`）—— **本 token 全部可用**

| 路径 | 说明 | 关键参数 | 返回核心字段 |
|---|---|---|---|
| `/insights/patent-trends` | 年度申请/授权趋势 | `keywords`, `ipc`, `apply_start_time`, `apply_end_time`, `authority` | `year, application, granted, percentage` |
| `/insights/word-cloud` | 高频词云（近 5000 篇） | `keywords`, `lang` (en/cn) **必填** | `name, count` |
| `/insights/wheel-of-innovation` | 创新轮（二级关键词） | `keywords`, `lang` 必填 | 二级树状 |
| `/insights/priority-country` | 优先权国家分布 | `keywords` | `country, count, percentage` |
| `/insights/most-cited` | 被引用最多 Top10 | `keywords` | `patent_num, patent_id, title, count` |
| `/insights/inventor-ranking` | Top 发明人 | `keywords` | `name, count` |
| `/insights/applicant-ranking` | Top 申请人/公司 | `keywords`, `lang` 必填 | `applicant, count, percentage` |
| `/insights/simple-legal-status` | 整体法律状态分布 | `keywords` | `simple_legal_status, count` |
| `/insights/most-asserted` | 最常被诉 Top10 | `keywords` | `patent_num, patent_id, title, count` |
| `/insights/portfolio-value` | 价值区间分布 | `keywords` | `patent_value, count` |

公共可选过滤：`ipc`, `apply_start_time/apply_end_time`, `public_start_time/public_end_time`, `authority`（CN/US/EP/JP/...）。时间格式实测接受 4 位年份（如 `2020`）。

### 3.2 Search 检索（`POST /search/patent/*`）—— **本 token 仅 count 类可用**

| 路径 | 说明 | 本 token 状态 |
|---|---|---|
| `/search/patent/query-search-count` | 命中量统计 | ✅ 可用 |
| `/search/patent/search` | 检索式拉记录 | ❌ `67200203` 未授权 |
| `/search/patent/search-filter` | 检索+筛选 | ❌ |
| `/search/patent/applicant` | 按申请人 | ❌ |
| `/search/patent/assignee` | 按权利人 | ❌ |
| `/search/patent/similar-by-pn` | 按号查相似 | ❌ |
| `/search/patent/semantic-search` | 语义相似 | ❌ |
| `/search/patent/standard-pn-query` | 标准化专利号 | ❌ |
| `/search/patent/keyword-assistant` | 关键词建议 | ❌ |

`query_text` 语法支持 PatSnap 检索式（`TTL:`, `TACD:`, `PN:`, `APD:[20240101 TO 20251231]`, AND/OR/NOT、引号短语等）。

### 3.3 Basic Patent Data 单专利数据（`GET /basic-patent-data/*`）—— **本 token 仅 legal-status 系列可用**

| 路径 | 说明 | 必填参数 | 本 token |
|---|---|---|---|
| `/basic-patent-data/legal-status` | 详细法律状态（含 patent_legal） | `patent_number` | ✅ |
| `/basic-patent-data/simple-legal-status` | 简化法律状态（有效/失效/审中） | `patent_number` | ✅ |
| `/basic-patent-data/biblio` | 著录项 | `patent_number` | ❌ `67200203` |
| `/basic-patent-data/abstract` | 摘要 | `patent_number` | ❌ |
| `/basic-patent-data/family` | 同族 | `patent_number` | ❌ |
| `/basic-patent-data/citation` | 引证 | `patent_number` | ❌ |
| `/basic-patent-data/cited` | 被引证 | `patent_number` | ❌ |
| `/basic-patent-data/claim` | 权利要求 | `patent_number` | ❌ |
| `/basic-patent-data/description` | 说明书 | `patent_number` | ❌ |

⚠️ 参数名是 `patent_number`，**不是** `pn` 或 `patent_id`（用 `pn` 会过、用 `patent_id` 返回空数组）。

### 3.4 文档全部分类（仅文档级，未逐一实测）

- 专利数据检索 22 个端点
- 专利基础数据 17 个
- 专利挖掘数据 11 个 ← 本 token 已开 10/10
- 专利法律详情 13 个
- 专利价值评估 10 个
- 商标 3 个
- 企业 14 个
- 生物医药 / 药物研发
- 自定义聚合数据 25 个

---

## 4. 限速与计费（文档摘要）

- **整体 QPS 限流** + **每日配额**，二者按客户号配置。
- **按调用计费**："查得计费"（成功返回结果才扣费）；图像检索一次出错不扣，是普遍约定。
- 文档明示：正常响应 ~5000ms，超时上限 10000ms。
- 错误码 `67200002` (限流)、`67200007` (配额耗尽)、`67200203` (端点未购) 是三大限流类。
- 无 OAuth 刷新机制；密钥静态长期有效，建议环境变量 + 定期轮换。

---

## 5. 实测 3 个端点的请求/响应样例（token 脱敏）

### 5.1 `query-search-count`：检索式命中量（中文）

请求：
```bash
curl -X POST "https://connect.zhihuiya.com/search/patent/query-search-count" \
  -H "Authorization: Bearer ${ZHIHUIYA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query_text":"TACD: 大语言模型"}'
```
响应：
```json
{ "status": true, "error_code": 0,
  "data": { "total_search_result_count": 68960 } }
```
另一组：`TACD: "大语言模型" AND APD:[20240101 TO 20251231]` → 60,032 条；`PN: CN114972869A` → 1 条。

### 5.2 `basic-patent-data/legal-status`：单专利法律状态

请求：
```bash
curl "https://connect.zhihuiya.com/basic-patent-data/legal-status?patent_number=CN114972869A" \
  -H "Authorization: Bearer ${ZHIHUIYA_TOKEN}"
```
响应：
```json
{
  "status": true, "error_code": 0,
  "data": [{
    "patent_id": "2fd3da0b-ee2c-40fa-87bc-0828eae5d1de",
    "pn": "CN114972869A",
    "legal_date": 20240220,
    "patent_legal": {
      "simple_legal_status": ["有效"],
      "legal_status": ["授权"]
    }
  }]
}
```
关键产出：拿到 `patent_id`（PatSnap 内部 UUID），后续详情类接口需要它做主键。

### 5.3 `insights/patent-trends`：lithium battery 在 CN 的 2020-2024 趋势

请求：
```bash
curl "https://connect.zhihuiya.com/insights/patent-trends?keywords=lithium%20battery&apply_start_time=2020&apply_end_time=2024&authority=CN" \
  -H "Authorization: Bearer ${ZHIHUIYA_TOKEN}"
```
响应（节选）：
```json
{ "status": true, "error_code": 0,
  "data": [
    {"year":"2020","application":86623,"granted":68345,"percentage":0.789},
    {"year":"2021","application":87748,"granted":66921,"percentage":0.7626},
    {"year":"2022","application":97956,"granted":68603,"percentage":0.7003},
    {"year":"2023","application":104478,"granted":62292,"percentage":0.5962},
    {"year":"2024","application":99247,"granted":54446,"percentage":0.5486}
  ]}
```

附加实测亮点：`/insights/applicant-ranking` 可直接拿到锂电赛道 Top 申请人（LG ES 25.3%、TOYOTA 19.1%、Samsung SDI 11.4%、CATL 8.2%……）；`/insights/most-cited` 直接给 Top10 高被引专利及 `patent_id`。

---

## 6. patent_king 集成建议

### 6.1 当前 token 的能力盘点

| 能力 | 状态 | 用法 |
|---|---|---|
| 任意检索式命中量 | ✅ | `query-search-count` |
| 单专利法律状态 | ✅ | `basic-patent-data/(simple-)legal-status` |
| 技术领域全景分析（10 维） | ✅ | `insights/*` 全开 |
| **拉取专利记录列表** | ❌ | search 系列被锁，需升级套餐 |
| 单专利全文/同族/引证 | ❌ | basic-patent-data 主体被锁 |

### 6.2 推荐的 3 个最重要端点（项目优先封装）

1. **`POST /search/patent/query-search-count`** — 任意检索式 → 命中量。  
   做"专利景气度温度计"、技术词验证（关键词是否能命中、能命中多少）。
2. **`GET /insights/patent-trends`** + `/insights/applicant-ranking` + `/insights/most-cited` 三件套 — 技术领域调研一键出图。  
   覆盖了"趋势 / 玩家 / 重点专利"的标准三连，是专家级技术调研的 80% 输出。
3. **`GET /basic-patent-data/simple-legal-status`** — 任一公开号 → patent_id + 有效性。  
   既是法律状态查询本身（高频刚需），也是把外部公开号映射到 PatSnap 内部 patent_id 的"路由表"——之后所有 detail 接口都靠它。

### 6.3 字段映射建议（与 patent_king 内部 schema）

| patent_king 概念 | 智慧芽字段 | 端点 |
|---|---|---|
| `pn` (公开号) | `pn` / `patent_num` | 全部 |
| `patent_id` (内部主键) | `patent_id` (UUID) | legal-status / insights |
| `legal_state` | `patent_legal.simple_legal_status[0]` | legal-status |
| `apply_year` | trends `year` + `application` | patent-trends |
| `top_assignee` | `applicant` | applicant-ranking（注意要传 `lang`） |
| `keyword_freq` | `name, count` | word-cloud（要传 `lang`） |

### 6.4 工程化注意事项

- **Base URL 修正**：`.env` 里的 `ZHIHUIYA_API_BASE=https://open.zhihuiya.com` 是文档站；实际调用必须用 `https://connect.zhihuiya.com`。建议在 `.env` 里改名为 `ZHIHUIYA_DOC_BASE`，新增 `ZHIHUIYA_API_BASE=https://connect.zhihuiya.com`，或在客户端硬编码 connect 域名。
- **业务层错误判断**：HTTP 200 + `status:false` 是常态；用 `error_code != 0` 路由到限流退避 / 套餐受限提示 / 参数错误。
- **`67200203` 退避策略**：标记该端点为本 key "未开通"，进 7 天黑名单避免无谓调用与扣费风险。
- **中文检索**：`keywords=` 直接 URL-encode 中文；`query_text` 也支持中文。检索式语法用 PatSnap 字段前缀（`TTL/TACD/PN/APD/AD/PD/IPC/AN`）。
- **Lang 参数**：`word-cloud` / `wheel-of-innovation` / `applicant-ranking` 必须带 `lang=cn|en`，缺则报 10001。
- **不需要做 MCP 包装**：patent_king 自己直接调 REST 即可；如果未来要把这套能力暴露给其它 Claude Code 用户，再考虑参考 KunihiroS 的 9 工具结构起一个 MCP server。

---

## 附录：错误码速查

| code | 含义 | 处理 |
|---|---|---|
| 0 | 成功 | — |
| 10001 | 必填参数缺失 | 补参 |
| 67200002 | QPS 限流 | 指数退避 |
| 67200007 | 日配额用尽 | 等次日 |
| 67200008 | 缺 apikey | 检查 header |
| 67200202 | apikey 校验失败 | 检查 host/key |
| 67200203 | 端点未购买 | 套餐黑名单 |
| 68300004 | patent 主键缺失 | 改用 `patent_number` 参数名 |

## 附录：参考链接
- 智慧芽开放平台首页：<https://open.zhihuiya.com/>
- API Reference：<https://open.zhihuiya.com/devportal/api-reference/>
- PatSnap 海外开放平台（同源）：<https://open.patsnap.com/>
- 官方 MCP：<https://open.patsnap.com/devportal/guides/mcp-overview>
- 三方 MCP（含全部 insights 端点参数清单）：<https://github.com/KunihiroS/patsnap-mcp>
