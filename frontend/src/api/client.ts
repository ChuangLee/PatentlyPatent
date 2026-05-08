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

const TOKEN_KEY = 'pp.auth.token';

// v0.21：req 自动注入 Bearer token
apiClient.interceptors.request.use(cfg => {
  const tk = typeof localStorage !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null;
  if (tk) {
    cfg.headers = cfg.headers || {};
    (cfg.headers as Record<string, string>)['Authorization'] = `Bearer ${tk}`;
  }
  return cfg;
});

// v0.21：401 → 清 token + 跳 /login（除登录接口本身）
apiClient.interceptors.response.use(
  r => r,
  err => {
    const status = err?.response?.status;
    const url: string = err?.config?.url || '';
    if (status === 401 && !url.includes('/auth/login')) {
      try {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem('pp.auth.user');
      } catch { /* noop */ }
      if (typeof window !== 'undefined' && !window.location.pathname.endsWith('/login')) {
        window.location.href = '/login';
      }
    }
    console.error('[api]', err.message);
    return Promise.reject(err);
  },
);
