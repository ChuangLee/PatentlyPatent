import { describe, it, expect, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';
import { setupGuards } from '@/router/guards';
import { useAuthStore } from '@/stores/auth';
import type { User } from '@/types';

const employee: User = { id: 'u1', name: 'A', role: 'employee', department: 'D' };
const admin: User = { id: 'u2', name: 'B', role: 'admin', department: 'D' };

function makeRouter() {
  const r = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', redirect: '/login' },
      { path: '/login', component: { template: '<div/>' } },
      { path: '/403', component: { template: '<div/>' } },
      { path: '/employee/x', component: { template: '<div/>' }, meta: { roles: ['employee', 'admin'] } },
      { path: '/admin/x', component: { template: '<div/>' }, meta: { roles: ['admin'] } },
    ],
  });
  setupGuards(r);
  return r;
}

describe('RBAC guards', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it('未登录访问受保护路径跳 login', async () => {
    const r = makeRouter();
    await r.push('/admin/x');
    expect(r.currentRoute.value.path).toBe('/login');
  });

  it('登录后访问允许的路径成功', async () => {
    const r = makeRouter();
    useAuthStore().login(employee);
    await r.push('/employee/x');
    expect(r.currentRoute.value.path).toBe('/employee/x');
  });

  it('员工访问 admin 路径 → 403', async () => {
    const r = makeRouter();
    useAuthStore().login(employee);
    await r.push('/admin/x');
    expect(r.currentRoute.value.path).toBe('/403');
  });

  it('admin 访问员工路径成功（兼具浏览权）', async () => {
    const r = makeRouter();
    useAuthStore().login(admin);
    await r.push('/employee/x');
    expect(r.currentRoute.value.path).toBe('/employee/x');
  });
});
