# PatentlyPatent 部署运维手册

> 一句话：**Vue 静态文件由 nginx 直供，FastAPI 后端走 systemd，agent 通过子进程 spawn `claude` CLI 走 OAuth 认证，数据落 SQLite WAL。** 公网入口 <https://blind.pub/patent>。
>
> 专利检索数据走 **A 路智慧芽托管 MCP**（首选，HTTP streamable）+ **B 路 Google BigQuery patents-public-data**（免费降级备选）。

---

## 1. 架构概览

```mermaid
flowchart LR
    U[浏览器用户] --> NG[nginx<br/>blind.pub/patent<br/>proxy_buffering off]
    NG -->|静态| S["/var/www/patent/<br/>Vue dist"]
    NG -->|/api/*| API[FastAPI :8088<br/>systemd unit<br/>uvicorn]
    API --> DB[(SQLite WAL<br/>backend/patentlypatent.db)]
    API -->|spawn| CLI[claude CLI<br/>子进程<br/>OAuth ~/.claude]
    CLI --> ANT[Anthropic API]
    CLI -->|A 路 MCP HTTP| ZHY[智慧芽 connect.zhihuiya.com<br/>logic-mcp + main-mcp]
    CLI -.A 业务错降级.-> BQ[Google BigQuery<br/>patents-public-data]
```

---

## 2. 部署目录约定

| 用途 | 路径 |
|---|---|
| 代码根 | `/root/ai-workspace/patent_king/` |
| 前端 dist | `/var/www/patent/` |
| Python venv | `/root/ai-workspace/patent_king/backend/.venv/` |
| SQLite DB | `/root/ai-workspace/patent_king/backend/patentlypatent.db` |
| docx 落盘 | `/root/ai-workspace/patent_king/backend/storage/{pid}/` |
| secrets | `.secrets/zhihuiya.env`（REST token + 托管 MCP URLs），`.secrets/gcp-bq.json`（B 路 BigQuery service account） |
| claude CLI 凭证 | `/root/.claude/.credentials.json` |

---

## 3. systemd 服务管理

- 服务名：`patentlypatent-backend.service`
- Unit 文件：`/etc/systemd/system/patentlypatent-backend.service`
- Override：`/etc/systemd/system/patentlypatent-backend.service.d/override.conf`
  - 关键 env：`PATH=/root/.local/bin:...`、`HOME=/root`、`PP_AGENT_PRIOR_ART=1`
  - PATH 必填，否则子进程 spawn `claude` 找不到二进制

```bash
sudo systemctl start    patentlypatent-backend
sudo systemctl stop     patentlypatent-backend
sudo systemctl restart  patentlypatent-backend
sudo systemctl status   patentlypatent-backend
sudo journalctl -u patentlypatent-backend -f          # 实时日志
sudo systemctl edit patentlypatent-backend            # 改 override.conf
sudo systemctl daemon-reload                          # 改完必须 reload
```

启动期会打印 claude CLI 路径 / 模型 / 智慧芽凭证 / BigQuery 凭证就位状态，作为冒烟自检。

**B 路 BigQuery 启用（一次性，按需）**：

```bash
# 1. 上传 GCP service account JSON 到 .secrets/gcp-bq.json，chmod 600
# 2. 在 https://console.developers.google.com/apis/api/bigquery.googleapis.com/overview?project=<PROJECT_ID> 启用 BigQuery API
# 3. systemd override 注入两个 env：
sudo tee /etc/systemd/system/patentlypatent-backend.service.d/bq.conf <<EOF
[Service]
Environment="GOOGLE_APPLICATION_CREDENTIALS=/root/ai-workspace/patent_king/.secrets/gcp-bq.json"
Environment="BQ_BILLING_PROJECT=<PROJECT_ID>"
EOF
sudo systemctl daemon-reload && sudo systemctl restart patentlypatent-backend
```

缺凭证时 `patents_bq.is_available()` 返 False，agent 看不到 BQ 工具，行为静默回退到 A 路。

---

## 4. nginx 反代

定位配置：

```bash
grep -rn "patent" /etc/nginx/sites-enabled/ /etc/nginx/sites-available/
```

关键点：
- `location /patent/` 静态指 `/var/www/patent/`，含 `try_files`
- `location /patent/api/` `proxy_pass http://127.0.0.1:8088/api/`
- **SSE 必加**：`proxy_buffering off;` `proxy_read_timeout 600s;` `proxy_set_header X-Accel-Buffering no;`
- 配置改后 `sudo nginx -t && sudo systemctl reload nginx`

---

## 5. claude CLI 认证管理

agent SDK 默认通过 Claude Code CLI 子进程跑，认证文件：

- 位置：`/root/.claude/.credentials.json`
- 401 / 过期处理：
  ```bash
  # 方案 A（生产默认）：复制 claude 用户的有效凭证
  sudo cp /home/claude/.claude/.credentials.json /root/.claude/.credentials.json.bak
  sudo cp /home/claude/.claude/.credentials.json /root/.claude/.credentials.json
  sudo systemctl restart patentlypatent-backend
  # 方案 B：以 root 重新走 OAuth（需要交互）
  sudo claude /login
  ```
- 验证：`curl -sN -X POST https://blind.pub/patent/api/agent/mine_spike -d '{"idea":"test"}'`，看到 `total_cost_usd=...` 非 mock 即通

---

## 6. 数据备份

```bash
# 手动一次
sqlite3 /root/ai-workspace/patent_king/backend/patentlypatent.db .dump \
  > /var/backups/patentlypatent/dump-$(date +%F).sql

# 推荐 cron（每日 02:00）
0 2 * * * sqlite3 /root/ai-workspace/patent_king/backend/patentlypatent.db .dump \
  | gzip > /var/backups/patentlypatent/dump-$(date +\%F).sql.gz \
  && find /var/backups/patentlypatent -name 'dump-*.sql.gz' -mtime +14 -delete
```

`backend/storage/{pid}/*.docx` 也建议同步 rsync 到备份目录。

---

## 7. 日志查看

| 来源 | 命令 |
|---|---|
| backend | `sudo journalctl -u patentlypatent-backend -f` |
| backend 历史 | `sudo journalctl -u patentlypatent-backend --since '1 hour ago'` |
| nginx access | `sudo tail -f /var/log/nginx/access.log` |
| nginx error | `sudo tail -f /var/log/nginx/error.log` |
| agent 监控 API | `curl -s 'https://blind.pub/patent/api/admin/agent_runs?limit=50' \| jq` |

agent_runs 字段：`endpoint / project_id / idea / num_turns / total_cost_usd / duration_ms / stop_reason / error`。

---

## 8. cost / 配额监控

- **每日 cost 预算**：`GET /api/admin/budget_status` 已实现，warn $2 / block $10
- **智慧芽 OpenAPI 余额**：控制台 <https://open.zhihuiya.com/> 后台→套餐管理。
  - 业务错 `67200005 Insufficient balance` / `67200004` **上抛**让 LLM 看见，SYSTEM_PROMPT 引导切 B 路 BigQuery；日志：`grep "Insufficient balance" -i ...`
  - 同接口连续 0 命中 + 67200005 大量出现 → 立即查套餐；search/insights/legal-status 套餐分开
- **B 路 BigQuery 配额**：免费层 1TB 扫描/月，本 adapter 默认 LIMIT 50 + 字段裁剪，日常远不到上限；监控 <https://console.cloud.google.com/billing>
- **Anthropic cost**：每次 agent 跑写 `agent_runs.total_cost_usd`，admin Dashboard echarts line 按 endpoint 分系列展示
- **OAuth 凭证状态**：`agent_runs` 表观察 `stop_reason='stop_sequence'` + `num_turns=1` + `cost=0` + delta 为空 → CLI 401，立即去 §5 刷凭证

---

## 9. 紧急处理

| 症状 | 处理 |
|---|---|
| 智慧芽连续 0 命中 + 误判蓝海 | curl `connect.zhihuiya.com/search/patent/query-search-count` 检验，若 67200005 → 后台续费 search/insights 套餐 |
| claude CLI 401（AI 不出回答只显示一句乱码） | `sudo cp /home/claude/.claude/.credentials.json /root/.claude/.credentials.json` 并 `systemctl restart`，过期参 §5 |
| 进项目永远"思考中"，但 ▶ 开始挖掘按钮没用过 | 数据库有僵死 running run（startup 自动清理一次）。手动：`UPDATE agent_runs SET status='cancelled' WHERE status='running'` 再 restart |
| 用户上传 PDF/pptx AI 看不到 | 检查 `backend/storage/uploads/<pid>/<fid>/` 文件是否在；`file_extract.py` 是否报错；老 `.doc/.ppt` 不支持需用户另存 |
| cost 单日 > $10 | budget 自动 503 阻断；查 admin Dashboard 看哪个 endpoint 烧最猛；调 `PP_DAILY_BUDGET_BLOCK` env 临时降 |
| 部署回滚 | `git revert <sha>` → 见 §10 全流程重 build/restart；DB 回滚用 §6 dump |
| 后端崩溃 | journalctl 看 traceback；常见：DB 锁（WAL 模式应不会）、claude CLI 子进程超时 |
| 项目"本系统文档"不显示 / 内容过期 | `system_docs.py:backfill_all_projects` 启动期幂等；改 `docs/*.md` 后 `systemctl restart` 自动推到所有项目；sessionStorage cache 升 v2 强制清旧 |

---

## 10. 升级流程

```bash
# 1. 拉代码
cd /root/ai-workspace/patent_king && git pull

# 2. 前端
cd frontend && pnpm install && pnpm build
sudo rsync -av --delete dist/ /var/www/patent/

# 3. 后端
cd ../backend && .venv/bin/pip install -r requirements.txt
sudo systemctl restart patentlypatent-backend

# 4. 自检
sleep 5
curl -sf https://blind.pub/patent/api/ping            # 期望 200 {"ok":true}
curl -sf https://blind.pub/patent/api/admin/agent_runs?limit=1 | jq .
```

如 `pnpm test` / `vue-tsc` / 后端 pytest 任一不过，**不要 deploy**，先修。

---

## 11. 日常巡检清单

```bash
# 后端启动日志 3 条关键
sudo journalctl -u patentlypatent-backend --since "5 min ago" --no-pager | grep -E "startup|system_docs|stale"
# 期望：
#   system_docs: backfilled N projects
#   startup ok | claude_cli=... | 智慧芽凭证就位 | BigQuery 凭证状态
#   (可选) marked X stale running AgentRun as cancelled

# 智慧芽余额自检
curl -sS -X POST "https://connect.zhihuiya.com/search/patent/query-search-count" \
  -H "Authorization: Bearer ${ZHIHUIYA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query":"TAC: (test)"}' | jq
# 期望 {"status":true,"error_code":0,"data":...}；67200005 即套餐到期

# Anthropic 凭证自检
sudo -u root /root/ai-workspace/patent_king/backend/.venv/lib/python3.12/site-packages/claude_agent_sdk/_bundled/claude --version

# 24h cost 监控
curl -s "https://blind.pub/patent/api/admin/budget_status" | jq
```

---

## 关键事实速查

- 端口：FastAPI `127.0.0.1:8088`（仅本地，nginx 反代外暴）
- 模型：`claude-opus-4-7` 主，`claude-sonnet-4-6` light
- LLM 凭证：仅 claude CLI OAuth（`/root/.claude/.credentials.json`），**不依赖 ANTHROPIC_API_KEY**
- 智慧芽：`.secrets/zhihuiya.env` 含 REST token + 托管 MCP URLs
- BigQuery：`.secrets/gcp-bq.json` + env `GOOGLE_APPLICATION_CREDENTIALS` + `BQ_BILLING_PROJECT`
- 静态部署：`/var/www/patent/`（nginx 直供，base=`/patent/`）
- DB：SQLite WAL `backend/patentlypatent.db`，并发读 + 单写
- 文件上传：`backend/storage/uploads/<pid>/<fid>/<name>`
- 智慧芽：仅走 A 路 hosted MCP（apikey 在 URL）；老 in-house REST 工具已下线
- SSE 并发：Semaphore 5；日预算 warn $2 / block $10
- agent SDK 默认 max_turns：interview 8 / mine_full 5

---

## CAS 对接

PatentlyPatent 支持 CAS protocol 2.0/3.0 单点登录，与 fake JWT 共存——前端 Login 页同时显示「员工/管理员一键登录」与「🏢 企业 CAS 登录」按钮（CAS 按钮仅在后端 `cas_enabled=true` 时出现）。

### 1. 环境变量（4 个）

| 变量 | 作用 | 示例值 |
|---|---|---|
| `PP_CAS_ENABLED` | 总开关，`1`/`true` 启用 | `1` |
| `PP_CAS_SERVER` | CAS server 根（不带 `/login`） | `https://cas.your-corp.com/cas` |
| `PP_CAS_SERVICE` | 后端 callback 完整 URL（CAS server 必须 whitelist 这个 service URL） | `https://blind.pub/patent/api/auth/cas/callback` |
| `PP_CAS_FRONT_REDIRECT` | 前端登录页完整 URL；后端拿到 token 后 302 这里 | `https://blind.pub/patent/login` |

写到 `.secrets/cas.env` 或 systemd unit 的 `Environment=` 里。改完 `systemctl restart patentlypatent-backend`。

### 2. 流程图

```mermaid
sequenceDiagram
    participant U as 浏览器
    participant FE as Vue Login.vue
    participant API as FastAPI
    participant CAS as CAS Server
    U->>FE: 点 "🏢 企业 CAS 登录"
    FE->>API: GET /api/auth/cas/login
    API-->>U: 302 → CAS_SERVER/login?service=...
    U->>CAS: 登录表单
    CAS-->>U: 302 → /api/auth/cas/callback?ticket=ST-xxx
    U->>API: GET /api/auth/cas/callback?ticket=ST-xxx
    API->>CAS: GET /p3/serviceValidate?service=...&ticket=ST-xxx
    CAS-->>API: XML <cas:user>...</cas:user>
    API->>API: 查/建 User → 发 JWT
    API-->>U: 302 → FRONT_REDIRECT?token=&user=
    U->>FE: 解 query → store.consumeCasCallback() → 跳 dashboard
```

### 3. CAS 返回 XML 字段

后端用 `defusedxml` 解析以下字段（namespace `http://www.yale.edu/tp/cas`）：

- `cas:authenticationSuccess/cas:user` —— 必须；作为 `User.id`
- `cas:authenticationSuccess/cas:attributes/cas:displayName`（可选）—— 取作 `User.name`
- `cas:authenticationSuccess/cas:attributes/cas:department`（可选）—— 取作 `User.department`
- `cas:authenticationFailure` 出现 → 视为 ticket 无效

DB 中查不到该 username 时**自动创建** `role='employee'`、`department=attrs.department or 'CAS 接入'`。

### 4. ticket 时间窗

CAS Service Ticket 默认 5 分钟内有效且**只能消费一次**。后端 callback 必须在 5min 内调 `serviceValidate`，否则会拿到 `INVALID_TICKET`，前端跳 `?cas_error=invalid_ticket`。

### 5. 测试 CAS server

- 公开 demo：`https://casdoor.org`（Casdoor 内置 CAS server，需先在控制台建一个 application 并把 `service` 加到白名单），或公司内部 CAS。
- 不建议依赖公开 demo 做 prod；prod 必须走企业自有 CAS。
- 没有真 CAS 时本地用 `backend/tests/test_auth_cas.py` 跑 6 个单测（用 `httpx.MockTransport` 模拟 CAS XML）：

```bash
cd backend
PP_MOCK_LLM=1 PP_CAS_ENABLED=1 .venv/bin/pytest tests/test_auth_cas.py -v
```

### 6. 后端 endpoint

| 方法 | URL | 作用 |
|---|---|---|
| GET | `/api/auth/cas/login` | 302 跳 CAS server |
| GET | `/api/auth/cas/callback?ticket=...` | CAS 回调 → 验票 → 发 JWT → 跳前端 |
| GET | `/api/auth/cas/logout` | 跳 CAS server `/logout`（前端跳前应自行清 localStorage token） |

### 7. 故障排查

| 症状 | 检查 |
|---|---|
| 点按钮无反应 | 控制台看 `apiClient` 路径；确认 `cas_enabled=true`（curl `/api/ping`） |
| 跳到 CAS 后白屏 | CAS server 是否 whitelist `PP_CAS_SERVICE` |
| 回前端时 `?cas_error=invalid_ticket` | ticket 已被消费/过期；让用户重新发起 |
| 回前端时 `?cas_error=server_unreachable` | 后端日志 grep `cas validate request failed`；网络/DNS/CA 证书问题 |
| 回前端时 token 拿到但 401 | JWT secret 改过；DB 中无 user 但 auto-create 失败（看 backend log） |
