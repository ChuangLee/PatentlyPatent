# PatentlyPatent · L4 端到端测试 (Playwright)

5 条关键 user journey，默认跑公网部署 `https://blind.pub/patent`。

## 本地运行

```bash
cd frontend
# 首次：装依赖 + 装 chromium（仅 chromium 节省空间）
pnpm install
npx playwright install chromium

# 跑全部 e2e
npx playwright test --project=chromium

# 跑单条
npx playwright test journey.spec.ts -g "3b"

# headed 调试 + 慢速演示
npx playwright test --headed --slow-mo=500
```

## 切换环境

环境变量 `PP_E2E_BASE` 覆盖 baseURL：

```bash
# staging
PP_E2E_BASE=https://stg.blind.pub/patent npx playwright test
# 本地 vite dev
PP_E2E_BASE=http://localhost:5173/patent npx playwright test
```

## 失败时怎么看

- HTML 报告：`frontend/playwright-report/index.html`
- 失败 trace：`test-results/<spec>/trace.zip` → `npx playwright show-trace trace.zip`
- 截图 / 视频：`test-results/<spec>/`（首次失败截图，重试时录视频）

## 5 条 journey

1. **3a** 账密登录 → 跳 `/employee/dashboard`
2. **3b** 新建报门 → 工作台 → SSE 自动启动 → chat bubble 出非空内容（**复现 v0.34 卡空气泡 bug**）
3. **3c** 文件上传（fake PDF）→ 文件树点击预览
4. **3d** 暗色模式切换 → `<html data-theme="dark">`
5. **3e** 专利知识 sidebar 展开 → 打开 .md → modal 标题含 📚

## 注意

- **不要在 CI 跑**：耗时 + 占公网带宽 + 写真后端。手动 trigger。
- 测试用唯一时间戳标题，不主动清理生产数据（数据量小，可由管理员定期清）。
- `workers: 1` 串行，避免 sqlite 并发污染。
- `retries: 1`：抗一次性 SSE 抖动；真 bug 仍能稳定复现。
