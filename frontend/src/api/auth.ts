import { apiClient } from './client';
import type { User, Role } from '@/types';

export interface LoginResponse {
  token: string;
  user: User;
}

export const authApi = {
  /** v0.21：JWT 登录。后端返 {token, user}；失败时 fallback 到老 /login-as 仅取 user。 */
  loginAs: async (role: Role, userId?: string): Promise<LoginResponse> => {
    try {
      const r = await apiClient.post<LoginResponse>('/auth/login', { role, userId });
      return r.data;
    } catch (e) {
      // 兼容 MSW / 老后端：退到 /login-as 只拿 user，token 留空
      const r = await apiClient.post<User>('/auth/login-as', { role });
      return { token: '', user: r.data };
    }
  },
  me: () => apiClient.get<User>('/auth/me').then(r => r.data),
};
