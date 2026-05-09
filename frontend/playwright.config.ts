import { defineConfig, devices } from '@playwright/test';

/**
 * PatentlyPatent v0.35 — Playwright L4 端到端测试配置
 *
 * 默认 baseURL 指向公网部署 https://blind.pub/patent，可通过环境变量
 * PP_E2E_BASE 切换到 staging / 本地（如 http://localhost:5173/patent）。
 *
 * - fullyParallel: false / workers: 1：避免 sqlite 后端的并发污染（同账号串行最稳）。
 * - retries: 1：抗一次性 SSE 偶发抖动，但仍能暴露真实 bug。
 * - trace/video/screenshot：失败/重试时保留，方便定位 v0.34 卡空气泡 bug。
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  retries: 1,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.PP_E2E_BASE || 'https://blind.pub/patent',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15000,
    navigationTimeout: 30000,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
