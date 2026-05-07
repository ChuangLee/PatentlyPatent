import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { User, Role } from '@/types';

const KEY = 'pp.auth.user';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(loadUser());

  function loadUser(): User | null {
    if (typeof localStorage === 'undefined') return null;
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    try { return JSON.parse(raw) as User; } catch { return null; }
  }

  function login(u: User) {
    user.value = u;
    localStorage.setItem(KEY, JSON.stringify(u));
  }

  function logout() {
    user.value = null;
    localStorage.removeItem(KEY);
  }

  const role = computed<Role | null>(() => user.value?.role ?? null);
  const isAuthenticated = computed(() => user.value !== null);

  return { user, role, isAuthenticated, login, logout };
});
