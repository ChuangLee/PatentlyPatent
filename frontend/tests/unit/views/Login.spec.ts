import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { createRouter, createMemoryHistory } from 'vue-router';
import Login from '@/views/login/Login.vue';

// 模拟 axios apiClient（避免真打 /ping）
vi.mock('@/api/client', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: { cas_enabled: false } }),
    post: vi.fn(),
  },
}));

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: { template: '<div/>' } },
      { path: '/employee/dashboard', name: 'emp', component: { template: '<div/>' } },
      { path: '/admin/dashboard', name: 'adm', component: { template: '<div/>' } },
    ],
  });
}

describe('Login.vue 界面测试', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('账密表单输入框可见 + 演示账号提示展示', async () => {
    const router = makeRouter();
    router.push('/login');
    await router.isReady();
    const w = mount(Login, { global: { plugins: [router, createPinia()] } });
    await flushPromises();

    const html = w.html();
    expect(html).toContain('用户名');
    expect(html).toContain('密码');
    expect(html).toContain('user / user123');
    expect(html).toContain('admin / admin123');
  });

  it('账密表单含 username + password 两个输入位 + 登录提交按钮', async () => {
    const router = makeRouter();
    router.push('/login');
    await router.isReady();
    const w = mount(Login, { global: { plugins: [router, createPinia()] } });
    await flushPromises();

    const html = w.html();
    // 用户名输入（autocomplete=username）
    expect(html).toMatch(/autocomplete="username"|placeholder="用户名"/);
    // 密码输入（autocomplete=current-password）
    expect(html).toMatch(/autocomplete="current-password"|placeholder="密码"/);
    // 提交按钮（html-type=submit）
    expect(html).toMatch(/type="submit"|submit/);
  });

  it('cas_enabled=false 时不显示 CAS 按钮', async () => {
    const router = makeRouter();
    router.push('/login');
    await router.isReady();
    const w = mount(Login, { global: { plugins: [router, createPinia()] } });
    await flushPromises();
    expect(w.html()).not.toContain('使用企业 CAS 登录');
  });
});
