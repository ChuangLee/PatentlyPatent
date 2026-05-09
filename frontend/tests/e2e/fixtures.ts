import { test as base, expect, type Page } from '@playwright/test';

/**
 * 共用 fixture：
 *   authedPage  — 以员工 user/user123 登录后跳到 /employee/dashboard 的 Page
 *   adminPage   — 以管理员 admin/admin123 登录的 Page
 *
 * 备注：deployed baseURL 是 https://blind.pub/patent，Vue 路由 base 是 /patent
 *       但前端代码里 router.push('/employee/...') 对应的最终 URL 是
 *       /patent/employee/...。Playwright 的 baseURL 已包含 /patent，所以
 *       page.goto('/employee/dashboard') 这种相对路径写法不会自动拼上 base —
 *       因此这里统一用 page.goto('/patent/...') 或基于 baseURL 的相对补齐。
 *       为了简单一致，goto/waitForURL 都使用绝对子路径，比如 '/patent/login'。
 */

export const APP_BASE_PATH = '/patent';
export const ROUTE = {
  login: `${APP_BASE_PATH}/login`,
  employeeDashboard: `${APP_BASE_PATH}/employee/dashboard`,
  adminDashboard: `${APP_BASE_PATH}/admin/dashboard`,
};

export async function loginAs(page: Page, username: string, password: string) {
  await page.goto(ROUTE.login);
  // 等 input 渲染（首次进 SPA 路由可能略慢）
  await page.waitForSelector('input[autocomplete="username"]', { timeout: 15000 });
  await page.fill('input[autocomplete="username"]', username);
  await page.fill('input[autocomplete="current-password"]', password);
  // antd 在中文 2 字 button 文本里自动插空格 → "登 录"；用 getByRole 可正则匹配
  await page.getByRole('button', { name: /登\s*录/ }).first().click();
}

type Fixtures = {
  authedPage: Page;
  adminPage: Page;
};

export const test = base.extend<Fixtures>({
  authedPage: async ({ page }, use) => {
    await loginAs(page, 'user', 'user123');
    await page.waitForURL(/\/employee\/dashboard/, { timeout: 20000 });
    await use(page);
  },
  adminPage: async ({ page }, use) => {
    await loginAs(page, 'admin', 'admin123');
    await page.waitForURL(/\/admin\/dashboard/, { timeout: 20000 });
    await use(page);
  },
});

export { expect };
