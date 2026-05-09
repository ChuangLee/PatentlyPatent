import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { User, Role } from '@/types';

const KEY = 'pp.auth.user';
const TOKEN_KEY = 'pp.auth.token';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(loadUser());
  const token = ref<string | null>(loadToken());

  function loadUser(): User | null {
    if (typeof localStorage === 'undefined') return null;
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    try { return JSON.parse(raw) as User; } catch { return null; }
  }

  function loadToken(): string | null {
    if (typeof localStorage === 'undefined') return null;
    return localStorage.getItem(TOKEN_KEY);
  }

  /** v0.21：发后端 /auth/login 拿 JWT；UI 上仍然按 role 一键登录。 */
  async function loginAs(role: Role): Promise<User> {
    // 动态 import 避免循环依赖
    const { authApi } = await import('@/api/auth');
    const { token: tk, user: u } = await authApi.loginAs(role);
    user.value = u;
    token.value = tk || null;
    localStorage.setItem(KEY, JSON.stringify(u));
    if (tk) localStorage.setItem(TOKEN_KEY, tk);
    else localStorage.removeItem(TOKEN_KEY);
    return u;
  }

  /** v0.28：账号 + 密码登录 */
  async function loginWithPassword(username: string, password: string): Promise<User> {
    const { authApi } = await import('@/api/auth');
    const { token: tk, user: u } = await authApi.loginWithPassword(username, password);
    user.value = u;
    token.value = tk || null;
    localStorage.setItem(KEY, JSON.stringify(u));
    if (tk) localStorage.setItem(TOKEN_KEY, tk);
    else localStorage.removeItem(TOKEN_KEY);
    return u;
  }

  function login(u: User, tk?: string) {
    user.value = u;
    localStorage.setItem(KEY, JSON.stringify(u));
    if (tk) {
      token.value = tk;
      localStorage.setItem(TOKEN_KEY, tk);
    }
  }

  function logout() {
    user.value = null;
    token.value = null;
    localStorage.removeItem(KEY);
    localStorage.removeItem(TOKEN_KEY);
  }

  /** v0.23：跳后端 CAS 入口（后端会再 302 到 CAS server）。 */
  function loginViaCas() {
    const base = (import.meta.env.VITE_API_BASE as string | undefined) || '/api';
    window.location.href = `${base}/auth/cas/login`;
  }

  /** v0.23：从 CAS 回调 URL 的 ?token=...&user=... 取出并落地，返回 user。 */
  function consumeCasCallback(query: URLSearchParams): User | null {
    const tk = query.get('token');
    const userRaw = query.get('user');
    if (!tk || !userRaw) return null;
    try {
      const u = JSON.parse(userRaw) as User;
      user.value = u;
      token.value = tk;
      localStorage.setItem(KEY, JSON.stringify(u));
      localStorage.setItem(TOKEN_KEY, tk);
      return u;
    } catch {
      return null;
    }
  }

  const role = computed<Role | null>(() => user.value?.role ?? null);
  const isAuthenticated = computed(() => user.value !== null);

  return {
    user, token, role, isAuthenticated,
    login, loginAs, loginWithPassword, logout,
    loginViaCas, consumeCasCallback,
  };
});
