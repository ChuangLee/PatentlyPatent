# PatentlyPatent 部署运维手册 (v0.21)

> 一句话：**Vue 静态文件由 nginx 直供，FastAPI 后端走 systemd，agent 通过子进程 spawn `claude` CLI 走 OAuth 认证，数据落 SQLite WAL。** 公网入口 <https://blind.pub/patent>。

---

## 1. 架构概览

```mermaid
flowchart LR
    U[浏览器用户] --> NG[nginx<br/>blind.pub/patent<br/>proxy_buffering off]
    NG -->|静态| S[/var/www/patent/<br/>Vue dist]
    NG -->|/api/*| API[FastAPI :8088<br/>systemd unit<br/>uvicorn]
    API --> DB[(SQLite WAL<br/>backend/patentlypatent.db)]
    API -->|spawn| CLI[claude CLI<br/>子进程<br/>OAuth ~/.claude]
    CLI --> ANT[Anthropic API]
    API -->|httpx| ZHY[智慧芽 OpenAPI]
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
| secrets | `.secrets/zhihuiya.env`，`.secrets/anthropic.env`（可选） |
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

启动期会打印：`agent_sdk_spike: use_real_llm=False has_key=False use_real_zhihuiya=True` 等环境状态，作为冒烟自检。

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
  # 方案 A（v0.18 已采用）：复制 claude 用户的有效凭证
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

agent_runs 字段：`endpoint / project_id / idea / num_turns / total_cost_usd / duration_ms / stop_reason / fallback_used / error / is_mock`。

---

## 8. cost / 配额监控

- **每日 cost 预算**：`GET /api/admin/budget_status`（v0.21 计划新增；当前代码未找到该端点，待补齐）
- **智慧芽配额**：智慧芽控制台 <https://analytics.zhihuiya.com/> 查 OpenAPI 调用次数；本系统已加 LRU/TTL cache（300s/256 entries）+ 4 场景错误兜底，超限会 graceful 返空
- **Anthropic cost**：每次 agent 跑写 `agent_runs.total_cost_usd`，admin Dashboard echarts line 按 endpoint 分系列展示

---

## 9. 紧急处理

| 症状 | 处理 |
|---|---|
| agent fallback 率 > 30% | `sudo systemctl edit patentlypatent-backend` 关 `PP_AGENT_PRIOR_ART=0` → `daemon-reload` + `restart`，回退老 mining |
| cost 单日 > $10 | 临时降阈值：override 加 `Environment=PP_DAILY_BUDGET_BLOCK=5` → restart（需后端实现该 env 守卫，v0.21 待补） |
| 智慧芽 401 | 检查 `.secrets/zhihuiya.env` token 是否过期，重启后端 |
| claude CLI 401 | 见 §5 复制凭证或 `sudo claude /login` |
| 部署回滚 | `git revert <sha>` → 见 §10 全流程重 build/restart；DB 回滚用 §6 dump |
| 后端崩溃 | journalctl 看 traceback；常见：DB 锁（WAL 模式应不会）、claude CLI 子进程超时 |

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

## 关键事实速查

- 端口：FastAPI `127.0.0.1:8088`（仅本地，nginx 反代外暴）
- 默认开关：`PP_AGENT_PRIOR_ART=1`（prior_art 走 agent SDK），其余 `PP_AGENT_EMBODIMENTS / PP_AGENT_CLAIMS / PP_AGENT_DRAWINGS / PP_AGENT_SUMMARY` 默认 OFF
- LRU cache TTL：300s，max 256 entries
- agent SDK 默认 max_turns：8

> TODO：`/api/admin/budget_status` 与 `PP_DAILY_BUDGET_BLOCK` env 守卫在 v0.21 计划中（iteration_log v0.20 末尾下轮目标），代码 grep 无匹配，部署前需确认是否上线，否则 §8 §9 相关条目为占位。

---

## CAS 对接 (v0.23)

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
