import axios from 'axios';

/**
 * 后端 base URL：
 *   - 开发：默认走相对路径 '/api'（被 Vite proxy 转发到本地 8088 后端，或被 MSW 拦截）
 *   - 生产部署到 blind.pub/patent/：相对 '/api' 经 nginx 转发到后端 :8088
 *
 * 控制是否启用 MSW：见 main.ts，VITE_USE_MSW=true 时启 MSW，否则全部走真后端。
 */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.response.use(
  r => r,
  err => {
    console.error('[api]', err.message);
    return Promise.reject(err);
  },
);
