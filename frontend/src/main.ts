import { createApp } from 'vue';
import { createPinia } from 'pinia';
import Antd from 'ant-design-vue';
import 'ant-design-vue/dist/reset.css';
import './styles/tokens.css';
import App from './App.vue';
import { createAppRouter } from './router';

async function enableMocking() {
  if (import.meta.env.MODE === 'test') return;
  // 仅当 VITE_USE_MSW=true 时启 MSW；默认（生产 / 本地接真后端）走真后端
  if (import.meta.env.VITE_USE_MSW !== 'true') {
    console.info('[boot] MSW 已禁用，走真后端 (baseURL=' + (import.meta.env.VITE_API_BASE || '/api') + ')');
    return;
  }
  const { worker } = await import('./mock/browser');
  await worker.start({
    serviceWorker: { url: '/patent/mockServiceWorker.js' },
    onUnhandledRequest: 'bypass',
  });
}

async function bootstrap() {
  await enableMocking();
  const app = createApp(App);
  app.use(createPinia());
  app.use(createAppRouter());
  app.use(Antd);
  app.mount('#app');
}

bootstrap();
