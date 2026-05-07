import { apiClient } from './client';
import type { User, Role } from '@/types';

export const authApi = {
  loginAs: (role: Role) =>
    apiClient.post<User>('/auth/login-as', { role }).then(r => r.data),
  me: () => apiClient.get<User>('/auth/me').then(r => r.data),
};
