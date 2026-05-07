import axios from 'axios';

export const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// 全局响应拦截：统一抛错
apiClient.interceptors.response.use(
  r => r,
  err => {
    console.error('[api]', err.message);
    return Promise.reject(err);
  },
);
