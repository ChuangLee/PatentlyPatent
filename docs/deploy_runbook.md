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
