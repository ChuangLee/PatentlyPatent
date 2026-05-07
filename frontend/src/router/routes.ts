import type { RouteRecordRaw } from 'vue-router';

// 占位：views 在 Task 11+ 写出，此处先用 dynamic import + 空组件兜底
const Empty = () => import('@/components/common/Empty.vue').catch(() =>
  Promise.resolve({ default: { template: '<div>{{ $route.path }}</div>' } }));

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/login' },

  {
    path: '/login',
    component: () => import('@/layouts/BlankLayout.vue').catch(() => Empty()),
    children: [
      { path: '', name: 'login', component: () => import('@/views/login/Login.vue').catch(() => Empty()) },
    ],
  },

  {
    path: '/employee',
    component: () => import('@/layouts/DefaultLayout.vue').catch(() => Empty()),
    meta: { roles: ['employee', 'admin'] }, // admin 可只读
    children: [
      { path: 'dashboard', name: 'employee-dashboard',
        component: () => import('@/views/employee/Dashboard.vue').catch(() => Empty()) },
      { path: 'projects/new', name: 'project-new',
        component: () => import('@/views/employee/ProjectNew.vue').catch(() => Empty()) },

      // 新：统一工作台
      { path: 'projects/:id/workbench', name: 'project-workbench',
        component: () => import('@/views/employee/ProjectWorkbench.vue').catch(() => Empty()) },

      // 旧路由：保留但重定向到 workbench（让旧链接不 404）
      { path: 'projects/:id/mining', redirect: to => `/employee/projects/${to.params.id}/workbench` },
      { path: 'projects/:id/search', redirect: to => `/employee/projects/${to.params.id}/workbench` },
      { path: 'projects/:id/disclosure', redirect: to => `/employee/projects/${to.params.id}/workbench` },
    ],
  },

  {
    path: '/admin',
    component: () => import('@/layouts/DefaultLayout.vue').catch(() => Empty()),
    meta: { roles: ['admin'] },
    children: [
      { path: 'dashboard', name: 'admin-dashboard',
        component: () => import('@/views/admin/Dashboard.vue').catch(() => Empty()) },
      { path: 'projects', name: 'admin-projects',
        component: () => import('@/views/admin/Projects.vue').catch(() => Empty()) },
    ],
  },

  {
    path: '/403',
    component: () => import('@/layouts/BlankLayout.vue').catch(() => Empty()),
    children: [{ path: '', name: 'forbidden',
      component: () => import('@/views/error/Forbidden.vue').catch(() => Empty()) }],
  },
  {
    path: '/:pathMatch(.*)*',
    component: () => import('@/layouts/BlankLayout.vue').catch(() => Empty()),
    children: [{ path: '', name: 'not-found',
      component: () => import('@/views/error/NotFound.vue').catch(() => Empty()) }],
  },
];
