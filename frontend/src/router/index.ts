import { createRouter, createWebHistory } from 'vue-router';
import { routes } from './routes';
import { setupGuards } from './guards';

export function createAppRouter() {
  const router = createRouter({
    history: createWebHistory('/patent/'),
    routes,
  });
  setupGuards(router);
  return router;
}
