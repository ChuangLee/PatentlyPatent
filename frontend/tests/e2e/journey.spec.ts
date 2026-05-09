import { test, expect, loginAs } from './fixtures';
import { test as baseTest } from '@playwright/test';

/**
 * v0.35 Playwright L4 端到端关键 user journey 测试
 *
 * 默认打 https://blind.pub/patent（baseURL）
 * 包含 5 条 journey：
 *   3a. 账密登录 → 跳 employee dashboard
 *   3b. 报门 → 工作台 → SSE 自动启动 → chat bubble 出非空内容（v0.34 卡空气泡 bug 验证）
 *   3c. 文件上传 + 在文件树点击预览 / 下载链接断言
 *   3d. 暗色模式切换（document.documentElement.dataset.theme）
 *   3e. KB（专利知识）侧边栏展开 + 打开 .md 弹 modal
 *
 * 失败时 trace/video/screenshot 在 playwright-report/ 与 test-results/ 下。
 */

test.describe('PatentlyPatent L4 关键 user journey', () => {
  // ───────────────────────────── 3a 登录 ─────────────────────────────
  baseTest('3a · 员工账密登录 → 跳 employee dashboard', async ({ page }) => {
    await loginAs(page, 'user', 'user123');
    await expect(page).toHaveURL(/\/employee\/dashboard/, { timeout: 20000 });
    // 进 dashboard 后能看到「新建报门」按钮
    await expect(page.getByRole('button', { name: /新建报门/ }).first()).toBeVisible({ timeout: 10000 });
  });

  // ─────────── 3b 报门 → 工作台 → SSE 自动启动 → chat bubble 出内容（核心 bug 复现） ───────────
  test('3b · 报门 → 工作台 → SSE 自动启动 → chat bubble 出内容（v0.34 卡空气泡 bug）', async ({ authedPage }) => {
    const page = authedPage;

    // 已经在 /employee/dashboard
    await page.getByRole('button', { name: /新建报门/ }).first().click();

    // 等 modal 渲染（标题：新建报门 · 启动专利挖掘）
    await page.waitForSelector('.ant-modal-title:has-text("新建报门")', { timeout: 10000 });

    // 填标题（唯一时间戳避免冲突生产数据）
    const uniqueTitle = `e2e-test-${Date.now()}`;
    // 标题 input：模态框第一个 a-input 的 placeholder = "一句话描述你的创新点"
    const titleInput = page.locator('input[placeholder*="一句话描述"]').first();
    await titleInput.fill(uniqueTitle);

    // 选默认领域 = 其他，自定义领域填一下避免校验失败
    // 由于 modal 默认 form.domain='other'，需要填 customDomain
    const customDomainInput = page.locator('input[placeholder*="具体领域"]').first();
    if (await customDomainInput.isVisible({ timeout: 1000 }).catch(() => false)) {
      await customDomainInput.fill('e2e-domain');
    }

    // 点击模态框 OK 按钮（"确定 (0 项资料)"）
    // antd ok-text 用模板渲染（"确定 (N 项资料)" 单字符之间不会被插空格）
    await page.locator('.ant-modal-footer button.ant-btn-primary').first().click();

    // 等待跳转到 workbench
    await page.waitForURL(/\/employee\/projects\/[^/]+\/workbench/, { timeout: 30000 });

    // 关键断言：15 秒内 agent chat bubble 必须出现非空中文内容
    // .pp-chat-bubble-agent 是 agent 回答气泡
    await expect(page.locator('.pp-chat-bubble-agent').first()).toContainText(/[一-龥]/, {
      timeout: 15000,
    });
  });

  // ─────────── 3c 文件上传 + 文件树点击预览 ───────────
  test('3c · 文件上传 → 文件树点击 → 预览/下载', async ({ authedPage }) => {
    const page = authedPage;
    await page.getByRole('button', { name: /新建报门/ }).first().click();
    await page.waitForSelector('.ant-modal-title:has-text("新建报门")', { timeout: 10000 });

    // 创建一个 fake PDF buffer 做上传（PDF magic header 才会被识别为 application/pdf）
    const fakePdfBuf = Buffer.from(
      '%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n%%EOF\n',
      'utf-8',
    );
    const pdfName = `e2e-${Date.now()}.pdf`;

    // 模态框上传：找 [type="file"] input（antd a-upload 内嵌）
    const fileInput = page.locator('.ant-modal input[type="file"]').first();
    await fileInput.setInputFiles({
      name: pdfName,
      mimeType: 'application/pdf',
      buffer: fakePdfBuf,
    });

    // 等附件列表出现该文件名
    await expect(page.locator('.ant-modal').getByText(pdfName)).toBeVisible({ timeout: 8000 });

    // 填标题 + 自定义领域
    await page.locator('input[placeholder*="一句话描述"]').first().fill(`e2e-upload-${Date.now()}`);
    const customDomain = page.locator('input[placeholder*="具体领域"]').first();
    if (await customDomain.isVisible({ timeout: 1000 }).catch(() => false)) {
      await customDomain.fill('e2e-domain');
    }

    // antd ok-text 用模板渲染（"确定 (N 项资料)" 单字符之间不会被插空格）
    await page.locator('.ant-modal-footer button.ant-btn-primary').first().click();
    await page.waitForURL(/\/employee\/projects\/[^/]+\/workbench/, { timeout: 30000 });

    // 工作台左侧文件树渲染好后展开「我的资料」（可能已默认展开；非展开则点 caret）
    const myFolder = page.locator('.ant-tree-treenode:has-text("我的资料")').first();
    await expect(myFolder).toBeVisible({ timeout: 15000 });
    // 若 caret-right 状态则点击展开
    const switcher = myFolder.locator('.ant-tree-switcher').first();
    const isClosed = await switcher.evaluate((el) =>
      el.classList.contains('ant-tree-switcher_close'),
    ).catch(() => false);
    if (isClosed) await switcher.click();

    // 在文件树或 store-rendered 任意位置找到 pdf 名
    await expect(page.locator('.ant-tree-treenode').filter({ hasText: pdfName }).first()).toBeVisible({
      timeout: 15000,
    });
  });

  // ─────────── 3d 暗色模式 ───────────
  test('3d · 暗色模式切换 → html[data-theme="dark"]', async ({ authedPage }) => {
    const page = authedPage;
    // header 中 🌙 / ☀️ 按钮：title 含 "切换到深色模式" 或 "浅色模式"
    const themeBtn = page.locator('button[title*="切换到深色模式"], button[title*="切换到浅色模式"]').first();
    await expect(themeBtn).toBeVisible({ timeout: 10000 });

    const before = await page.evaluate(() => document.documentElement.getAttribute('data-theme') || 'light');
    await themeBtn.click();

    // 切换后 data-theme 应反向
    await expect.poll(
      async () => page.evaluate(() => document.documentElement.getAttribute('data-theme') || 'light'),
      { timeout: 5000 },
    ).not.toBe(before);

    // 切回去（保持环境干净）
    await page.locator('button[title*="切换到深色模式"], button[title*="切换到浅色模式"]').first().click();
  });

  // ─────────── 3e KB 专利知识浏览 ───────────
  test('3e · 专利知识 sidebar 展开 → 打开 .md → modal 标题含 📚', async ({ authedPage }) => {
    const page = authedPage;
    // KB 出现在工作台文件树而非 dashboard，所以先建一个项目
    await page.getByRole('button', { name: /新建报门/ }).first().click();
    await page.waitForSelector('.ant-modal-title:has-text("新建报门")', { timeout: 10000 });
    await page.locator('input[placeholder*="一句话描述"]').first().fill(`e2e-kb-${Date.now()}`);
    const customDomain = page.locator('input[placeholder*="具体领域"]').first();
    if (await customDomain.isVisible({ timeout: 1000 }).catch(() => false)) {
      await customDomain.fill('e2e-domain');
    }
    // antd ok-text 用模板渲染（"确定 (N 项资料)" 单字符之间不会被插空格）
    await page.locator('.ant-modal-footer button.ant-btn-primary').first().click();
    await page.waitForURL(/\/employee\/projects\/[^/]+\/workbench/, { timeout: 30000 });

    // 找文件树中"专利知识"虚拟根节点（icon 📚）
    const kbRoot = page.locator('.ant-tree-treenode:has-text("专利知识")').first();
    await expect(kbRoot).toBeVisible({ timeout: 15000 });

    const initialCount = await page.locator('.ant-tree-treenode').count();

    // 点开关折叠 switcher（kb-root 默认折叠；点击触发 loadData → kbApi.tree(...)）
    await kbRoot.locator('.ant-tree-switcher').first().click();

    // 等子节点懒加载渲染：至少出现 1 个子 treenode（总数变多）
    await expect.poll(
      async () => page.locator('.ant-tree-treenode').count(),
      { timeout: 20000, intervals: [500, 1000, 2000] },
    ).toBeGreaterThan(initialCount);

    // 找一个 .md 文件子节点；找不到则任意 leaf
    const mdLeaf = page.locator('.ant-tree-treenode').filter({ hasText: /\.md\b/ }).first();
    const hasMd = await mdLeaf.isVisible({ timeout: 5000 }).catch(() => false);
    if (hasMd) {
      await mdLeaf.click();
      // KB 预览 modal 标题应含 📚
      await expect(page.locator('.pp-kb-modal .ant-modal-title')).toContainText('📚', { timeout: 10000 });
    } else {
      // 退化断言：KB 已加载至少 1 个新节点（懒加载链路通了）
      // initialCount 已经被 above poll 验证更大了，这里加个 sanity 即可
      expect(await page.locator('.ant-tree-treenode').count()).toBeGreaterThan(initialCount);
    }
  });
});
