import { createApp } from 'vue';
import { createPinia } from 'pinia';
import Antd from 'ant-design-vue';
import 'ant-design-vue/dist/reset.css';
import './styles/tokens.css';
import App from './App.vue';
import { createAppRouter } from './router';

async function enableMocking() {
  if (import.meta.env.MODE === 'test') return;
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
