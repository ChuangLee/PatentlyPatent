import type { Router } from 'vue-router';
import type { Role } from '@/types';
import { useAuthStore } from '@/stores/auth';

export function setupGuards(router: Router) {
  router.beforeEach((to) => {
    const auth = useAuthStore();
    const path = to.path;

    // 公共
    if (path === '/login' || path === '/403' || path === '/not-found') return true;

    // 未登录 → 登录
    if (!auth.isAuthenticated) return { path: '/login' };

    // 角色检查
    const allowedRoles = (to.matched
      .flatMap(r => (r.meta?.roles as Role[] | undefined) ?? []));

    if (allowedRoles.length === 0) return true; // 无要求
    if (auth.role && allowedRoles.includes(auth.role)) return true;

    return { path: '/403' };
  });
}
