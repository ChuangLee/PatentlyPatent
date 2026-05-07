import { describe, it, expect, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useAuthStore } from '@/stores/auth';
import type { User } from '@/types';

describe('useAuthStore', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it('初始未登录', () => {
    const s = useAuthStore();
    expect(s.user).toBeNull();
    expect(s.isAuthenticated).toBe(false);
    expect(s.role).toBeNull();
  });

  it('login 持久化到 localStorage', () => {
    const s = useAuthStore();
    const u: User = { id: 'u1', name: 'A', role: 'employee', department: 'D' };
    s.login(u);
    expect(s.user).toEqual(u);
    expect(s.role).toBe('employee');
    expect(s.isAuthenticated).toBe(true);
    expect(JSON.parse(localStorage.getItem('pp.auth.user')!)).toEqual(u);
  });

  it('logout 清空', () => {
    const s = useAuthStore();
    s.login({ id: 'u1', name: 'A', role: 'admin', department: 'D' });
    s.logout();
    expect(s.user).toBeNull();
    expect(localStorage.getItem('pp.auth.user')).toBeNull();
  });

  it('从 localStorage 恢复', () => {
    const u: User = { id: 'u2', name: 'B', role: 'admin', department: 'D' };
    localStorage.setItem('pp.auth.user', JSON.stringify(u));
    const s = useAuthStore();
    expect(s.user).toEqual(u);
  });
});
