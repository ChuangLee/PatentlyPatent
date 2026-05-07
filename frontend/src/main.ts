import { createApp } from 'vue';
import { createPinia } from 'pinia';
import Antd from 'ant-design-vue';
import 'ant-design-vue/dist/reset.css';
import './styles/tokens.css';
import App from './App.vue';

async function bootstrap() {
  const app = createApp(App);
  app.use(createPinia());
  app.use(Antd);
  // router 在 Task 9 接入
  app.mount('#app');
}

bootstrap();
