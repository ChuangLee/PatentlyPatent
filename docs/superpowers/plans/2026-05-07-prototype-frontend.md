# PatentlyPatent v0 原型前端 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `frontend/` 子目录下用 Soybean Admin 模板基底（Vue 3 + Vite + Antd Vue 4 + TS + Pinia + vitest）搭一个 mid-fi 交互原型，用 MSW 拦截所有 API、伪流式 SSE 跑 agent 引导对话，员工跑通 4 阶段流程，管理员看分布；最终部署到 `https://blind.pub/patent/`。

**Architecture:** 纯前端 SPA + MSW 浏览器内 mock + service worker；axios 走 typed 接口（未来切真后端只换 baseURL）；pinia 4 个 store；vue-router history 模式 + RBAC 守卫；nginx alias 静态托管。

**Tech Stack:** Vue 3.5 / Vite 6 / TypeScript 5 / Pinia 2 / vue-router 4 / Ant Design Vue 4 / Tiptap 2 / ECharts 5 / MSW 2 / vitest 1 / axios 1 / pnpm 9

**Spec:** `docs/superpowers/specs/2026-05-07-prototype-frontend-design.md`

## 并行执行路线（Wave Plan）

任务按波次分组，**同波次内可并行 dispatch 多个 subagents**，波次间 sequential：

| Wave | Tasks | 并行度 | 关键依赖 |
|---|---|---|---|
| 1 | T1 项目骨架 | 1 | — |
| 2 | T2 数据模型, T3 MSW 初始化 | 2 | T1 |
| 3 | T4 Stores, T5 SSE utils, T6 Fixtures | **3** | T2, T3 |
| 4 | T7 API+Handlers, T8 Chat Handler, T9 Router+Guards | **3** | T2-T6 |
| 5 | T10 Layouts | 1 | T4, T9 |
| 6 | T11 Login + Dashboard + ProjectNew | 1 | T7, T10 |
| 7 | T12 Mining, T13 Search, T14 Disclosure, T15 Admin | **4** | T7, T8, T11 |
| 8 | T16 错误页 + 部署 | 1 | 全部 |

总计：**8 waves**，最大并行度 **4 agents/wave**，等价吞吐约 1.6× 串行（Amdahl law 限制）。

每波次完成后跑 `pnpm test && pnpm exec vue-tsc -b --noEmit`，全绿才进下一波。波次间无需用户确认；波次失败时 escalate。

---

## 文件清单

```
frontend/                                  # 项目根
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── vitest.config.ts
├── index.html
├── README.md
├── .gitignore
├── .eslintrc.cjs
├── public/
│   └── mockServiceWorker.js               # MSW 自动生成
├── scripts/
│   └── deploy.sh
├── nginx/
│   └── patent.conf.snippet
├── src/
│   ├── main.ts                            # 装配 + 启 MSW
│   ├── App.vue
│   ├── env.d.ts
│   ├── styles/
│   │   └── tokens.css
│   ├── types/
│   │   └── index.ts                       # 数据模型（TS interfaces）
│   ├── api/
│   │   ├── client.ts                      # axios 实例
│   │   ├── auth.ts
│   │   ├── projects.ts
│   │   ├── chat.ts
│   │   ├── search.ts
│   │   └── disclosure.ts
│   ├── stores/
│   │   ├── auth.ts                        # useAuthStore
│   │   ├── project.ts                     # useProjectStore
│   │   ├── chat.ts                        # useChatStore
│   │   └── ui.ts                          # useUIStore
│   ├── router/
│   │   ├── index.ts
│   │   ├── routes.ts
│   │   └── guards.ts
│   ├── layouts/
│   │   ├── DefaultLayout.vue              # 顶+侧栏壳
│   │   └── BlankLayout.vue                # login/403/404
│   ├── views/
│   │   ├── login/Login.vue
│   │   ├── employee/Dashboard.vue
│   │   ├── employee/ProjectNew.vue
│   │   ├── employee/ProjectMining.vue
│   │   ├── employee/ProjectSearch.vue
│   │   ├── employee/ProjectDisclosure.vue
│   │   ├── admin/Dashboard.vue
│   │   ├── admin/Projects.vue
│   │   └── error/Forbidden.vue
│   │   └── error/NotFound.vue
│   ├── components/
│   │   ├── chat/AgentChatStream.vue
│   │   ├── chat/MiningSummaryPanel.vue
│   │   ├── search/PatentabilityCards.vue
│   │   ├── search/HitsTable.vue
│   │   ├── disclosure/ClaimTierSelector.vue
│   │   ├── disclosure/TiptapEditor.vue
│   │   ├── common/RoleBadge.vue
│   │   └── common/ReadonlyBanner.vue
│   ├── mock/
│   │   ├── browser.ts                     # MSW worker setup
│   │   ├── utils.ts                       # sleep, splitByGrapheme, rand
│   │   ├── handlers/
│   │   │   ├── index.ts
│   │   │   ├── auth.ts
│   │   │   ├── projects.ts
│   │   │   ├── chat.ts
│   │   │   ├── search.ts
│   │   │   └── disclosure.ts
│   │   └── fixtures/
│   │       ├── users.ts
│   │       ├── case_crypto.ts
│   │       ├── case_infosec.ts
│   │       ├── case_ai.ts
│   │       └── all_cases.ts
│   └── utils/
│       └── sse.ts                         # SSE consumer
└── tests/
    ├── setup.ts
    └── unit/
        ├── stores/
        ├── router/
        ├── api/
        ├── mock/handlers/
        └── utils/
```

---

## Task 1：起项目骨架 + Vite/Router base 配置

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json` `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/.gitignore`
- Create: `frontend/src/main.ts` `frontend/src/App.vue` `frontend/src/env.d.ts`
- Create: `frontend/src/styles/tokens.css`

- [ ] **Step 1.1: 在项目根建 frontend 子目录并初始化 pnpm**

```bash
cd /root/ai-workspace/patent_king
mkdir -p frontend
cd frontend
pnpm init
```

- [ ] **Step 1.2: 写 package.json**

```json
{
  "name": "patentlypatent-prototype",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview --base /patent/",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "eslint . --ext .vue,.ts,.tsx --max-warnings 0",
    "deploy": "pnpm run build && bash scripts/deploy.sh"
  },
  "dependencies": {
    "vue": "^3.5.13",
    "vue-router": "^4.4.5",
    "pinia": "^2.3.0",
    "ant-design-vue": "^4.2.6",
    "@ant-design/icons-vue": "^7.0.1",
    "axios": "^1.7.9",
    "echarts": "^5.5.1",
    "@tiptap/vue-3": "^2.10.4",
    "@tiptap/starter-kit": "^2.10.4",
    "dayjs": "^1.11.13"
  },
  "devDependencies": {
    "@types/node": "^22.10.2",
    "@vitejs/plugin-vue": "^5.2.1",
    "@vue/test-utils": "^2.4.6",
    "@vue/tsconfig": "^0.7.0",
    "happy-dom": "^15.11.7",
    "msw": "^2.7.0",
    "typescript": "^5.7.2",
    "vite": "^6.0.7",
    "vitest": "^1.6.0",
    "vue-tsc": "^2.2.0"
  }
}
```

- [ ] **Step 1.3: 装依赖**

```bash
pnpm install
```
Expected: `pnpm-lock.yaml` 生成；node_modules 落地；无报错。

- [ ] **Step 1.4: 写 tsconfig.json**

```json
{
  "extends": "@vue/tsconfig/tsconfig.dom.json",
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] },
    "types": ["vite/client", "vitest/globals"]
  },
  "include": ["src/**/*", "src/**/*.vue", "tests/**/*"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 1.5: 写 tsconfig.node.json**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts", "vitest.config.ts"]
}
```

- [ ] **Step 1.6: 写 vite.config.ts**

```ts
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig(({ mode }) => ({
  base: '/patent/',
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    outDir: 'dist',
    sourcemap: mode === 'staging',
    chunkSizeWarningLimit: 1500,
  },
  server: { port: 5173, host: '127.0.0.1' },
}));
```

- [ ] **Step 1.7: 写 vitest.config.ts**

```ts
import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

export default mergeConfig(viteConfig, defineConfig({
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.spec.ts'],
  },
}));
```

- [ ] **Step 1.8: 写 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="robots" content="noindex, nofollow" />
    <title>PatentlyPatent · 原型</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 1.9: 写 src/env.d.ts**

```ts
/// <reference types="vite/client" />
declare module '*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<object, object, unknown>;
  export default component;
}
```

- [ ] **Step 1.10: 写 src/styles/tokens.css**

```css
:root {
  --pp-bg: #f5f5f5;
  --pp-fg: #1f2937;
  --pp-muted: #6b7280;
  --pp-accent: #1677ff;
  --pp-success: #16a34a;
  --pp-warn: #d97706;
  --pp-danger: #dc2626;
}
html, body, #app { margin: 0; height: 100%; }
body { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; }
```

- [ ] **Step 1.11: 写最简 src/App.vue**

```vue
<script setup lang="ts">
</script>
<template>
  <a-config-provider>
    <router-view />
  </a-config-provider>
</template>
```

- [ ] **Step 1.12: 写最简 src/main.ts（暂未启 MSW）**

```ts
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
```

- [ ] **Step 1.13: 写 .gitignore**

```
node_modules
dist
*.log
.vite
.env.local
.DS_Store
```

- [ ] **Step 1.14: 验证 dev server 跑起来**

```bash
cd frontend
pnpm dev
```
Expected: 终端显示 `Local: http://127.0.0.1:5173/patent/`，浏览器打开能看到空白页+无报错。Ctrl+C 关掉。

- [ ] **Step 1.15: 验证构建**

```bash
pnpm build
```
Expected: `dist/` 下生成 `index.html` `assets/*.js` `assets/*.css`，无 ts 报错。

- [ ] **Step 1.16: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/.gitignore frontend/package.json frontend/pnpm-lock.yaml \
  frontend/tsconfig.json frontend/tsconfig.node.json \
  frontend/vite.config.ts frontend/vitest.config.ts frontend/index.html \
  frontend/src/main.ts frontend/src/App.vue frontend/src/env.d.ts frontend/src/styles/tokens.css
git commit -m "feat(frontend): bootstrap Vite + Vue 3 + Antd Vue + Pinia, base=/patent/

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2：数据模型 + 测试基础设施

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/tests/setup.ts`
- Create: `frontend/tests/unit/types/index.spec.ts`

- [ ] **Step 2.1: 写 src/types/index.ts**

```ts
// 角色
export type Role = 'employee' | 'admin';

// 项目状态机
export type ProjectStatus = 'drafting' | 'researching' | 'reporting' | 'submitted';

// 技术领域
export type Domain = 'cryptography' | 'infosec' | 'ai' | 'other';

// 4 档专利性结论
export type Patentability = 'strong' | 'moderate' | 'weak' | 'not_recommended';

// 三档独权概括度
export type ClaimTier = 'broad' | 'medium' | 'narrow';

// 命中文献 X/Y/N 标注
export type XYNTag = 'X' | 'Y' | 'N';

export interface User {
  id: string;
  name: string;
  role: Role;
  department: string;
  avatar?: string;
}

export interface ChatMessage {
  id: string;
  role: 'agent' | 'user';
  content: string;
  ts: string;
  meta?: {
    stage?: '5why' | 'whatif' | 'generalize' | 'effect';
    capturedFields?: string[];
  };
}

export interface MiningSummary {
  field: string[];
  problem: string[];
  means: string[];
  effect: string[];
  differentiator: string[];
  conversation: ChatMessage[];
}

export interface PriorArtHit {
  id: string;
  title: string;
  abstract: string;
  applicant: string;
  pubDate: string;
  ipc: string[];
  xyn: XYNTag;
  comparison: { problem: string; means: string; effect: string };
  url?: string;
}

export interface SearchReport {
  patentability: Patentability;
  rationale: string;
  hits: PriorArtHit[];
}

export interface Disclosure {
  technicalField: string;
  background: string;
  summary: string;
  claims: { tier: ClaimTier; text: string; risk: string }[];
  drawingsDescription: string;
  embodiments: string;
  bodyMarkdown: string;
}

export interface Project {
  id: string;
  title: string;
  domain: Domain;
  description: string;
  status: ProjectStatus;
  ownerId: string;
  createdAt: string;
  updatedAt: string;
  miningSummary?: MiningSummary;
  searchReport?: SearchReport;
  disclosure?: Disclosure;
}

// SSE 事件类型
export type ChatStreamEvent =
  | { type: 'thinking' }
  | { type: 'delta'; chunk: string }
  | { type: 'fields'; captured: string[] }
  | { type: 'done' };
```

- [ ] **Step 2.2: 写 tests/setup.ts**

```ts
import { afterEach, beforeAll, afterAll } from 'vitest';

// 全局 setup（后续 MSW 在此初始化）
beforeAll(() => {
  // 占位
});

afterEach(() => {
  // 占位：清理 stores 等
});

afterAll(() => {
  // 占位
});
```

- [ ] **Step 2.3: 写 tests/unit/types/index.spec.ts（验证类型导出）**

```ts
import { describe, it, expectTypeOf } from 'vitest';
import type {
  Role, ProjectStatus, Domain, Patentability, ClaimTier, XYNTag,
  User, Project, ChatMessage, MiningSummary, SearchReport, PriorArtHit,
  Disclosure, ChatStreamEvent,
} from '@/types';

describe('types', () => {
  it('Role 是 employee | admin', () => {
    expectTypeOf<Role>().toEqualTypeOf<'employee' | 'admin'>();
  });

  it('ProjectStatus 4 状态', () => {
    expectTypeOf<ProjectStatus>().toEqualTypeOf<
      'drafting' | 'researching' | 'reporting' | 'submitted'
    >();
  });

  it('Project 必字段齐全', () => {
    const p: Project = {
      id: 'p1', title: 't', domain: 'ai', description: 'd',
      status: 'drafting', ownerId: 'u1',
      createdAt: '2026-05-07T00:00:00Z',
      updatedAt: '2026-05-07T00:00:00Z',
    };
    expectTypeOf(p).toMatchTypeOf<Project>();
  });

  it('ChatStreamEvent 4 种 discriminated union', () => {
    const e1: ChatStreamEvent = { type: 'thinking' };
    const e2: ChatStreamEvent = { type: 'delta', chunk: 'a' };
    const e3: ChatStreamEvent = { type: 'fields', captured: ['x'] };
    const e4: ChatStreamEvent = { type: 'done' };
    expectTypeOf([e1, e2, e3, e4]).toMatchTypeOf<ChatStreamEvent[]>();
  });
});
```

- [ ] **Step 2.4: 跑 vitest 验证**

```bash
cd frontend
pnpm test
```
Expected: 4 passed。

- [ ] **Step 2.5: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/types/index.ts frontend/tests/setup.ts frontend/tests/unit/types/index.spec.ts
git commit -m "feat(frontend): add TS data model + vitest setup

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3：装 MSW + 初始化 worker + 拦截 ping 端点验通

**Files:**
- Create: `frontend/src/mock/browser.ts`
- Create: `frontend/src/mock/handlers/index.ts`
- Create: `frontend/src/mock/utils.ts`
- Modify: `frontend/src/main.ts`
- Generate: `frontend/public/mockServiceWorker.js`（msw CLI）

- [ ] **Step 3.1: 用 msw CLI 生成 service worker 文件**

```bash
cd frontend
pnpm exec msw init public/ --save
```
Expected: 生成 `public/mockServiceWorker.js`，并在 package.json 写入 `msw.workerDirectory: ["public"]`。

- [ ] **Step 3.2: 写 src/mock/utils.ts**

```ts
export const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

export const rand = (min: number, max: number) =>
  Math.floor(Math.random() * (max - min + 1)) + min;

/** 把字符串按 grapheme（中文按字符）切成 size 大小的片，用于伪流式 chunk */
export function splitByGrapheme(text: string, size: number): string[] {
  const chars = Array.from(text); // Array.from 处理 unicode 比 split('') 更安全
  const out: string[] = [];
  for (let i = 0; i < chars.length; i += size) {
    out.push(chars.slice(i, i + size).join(''));
  }
  return out;
}
```

- [ ] **Step 3.3: 写 src/mock/handlers/index.ts**

```ts
import { http, HttpResponse } from 'msw';

// 占位 handlers，Task 7-8 会扩充
export const handlers = [
  http.get('/api/ping', () =>
    HttpResponse.json({ ok: true, msg: 'msw working' })
  ),
];
```

- [ ] **Step 3.4: 写 src/mock/browser.ts**

```ts
import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

export const worker = setupWorker(...handlers);
```

- [ ] **Step 3.5: 修改 src/main.ts 启 MSW**

```ts
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import Antd from 'ant-design-vue';
import 'ant-design-vue/dist/reset.css';
import './styles/tokens.css';
import App from './App.vue';

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
  app.use(Antd);
  // router 在 Task 9 接入
  app.mount('#app');
}

bootstrap();
```

- [ ] **Step 3.6: 临时改 App.vue 调 ping 验证**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue';

const result = ref<string>('loading...');

onMounted(async () => {
  const r = await fetch('/api/ping').then(x => x.json());
  result.value = JSON.stringify(r);
});
</script>
<template>
  <div style="padding:24px;font-family:monospace">
    <h1>PatentlyPatent · MSW smoke test</h1>
    <p>/api/ping → {{ result }}</p>
  </div>
</template>
```

- [ ] **Step 3.7: 跑 dev 验证**

```bash
cd frontend
pnpm dev
```
Open `http://127.0.0.1:5173/patent/`. Expected:
- 控制台有 `[MSW] Mocking enabled.`
- 页面显示 `/api/ping → {"ok":true,"msg":"msw working"}`
- DevTools → Application → Service Workers 看到注册的 worker

- [ ] **Step 3.8: 跑测试不被影响**

```bash
pnpm test
```
Expected: types spec 仍 pass；MSW 在 test 模式跳过启动。

- [ ] **Step 3.9: 把 App.vue 还原成最简版**

```vue
<script setup lang="ts">
</script>
<template>
  <a-config-provider>
    <router-view />
  </a-config-provider>
</template>
```

- [ ] **Step 3.10: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/public/mockServiceWorker.js frontend/src/mock/ frontend/src/main.ts frontend/src/App.vue frontend/package.json
git commit -m "feat(frontend): integrate MSW mock layer with smoke-tested ping endpoint

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4：4 个 Pinia stores（auth/project/chat/ui）+ tests

**Files:**
- Create: `frontend/src/stores/auth.ts`
- Create: `frontend/src/stores/project.ts`
- Create: `frontend/src/stores/chat.ts`
- Create: `frontend/src/stores/ui.ts`
- Create: `frontend/tests/unit/stores/auth.spec.ts`
- Create: `frontend/tests/unit/stores/project.spec.ts`
- Create: `frontend/tests/unit/stores/chat.spec.ts`
- Create: `frontend/tests/unit/stores/ui.spec.ts`

- [ ] **Step 4.1: 写 stores/auth.ts**

```ts
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { User, Role } from '@/types';

const KEY = 'pp.auth.user';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(loadUser());

  function loadUser(): User | null {
    if (typeof localStorage === 'undefined') return null;
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    try { return JSON.parse(raw) as User; } catch { return null; }
  }

  function login(u: User) {
    user.value = u;
    localStorage.setItem(KEY, JSON.stringify(u));
  }

  function logout() {
    user.value = null;
    localStorage.removeItem(KEY);
  }

  const role = computed<Role | null>(() => user.value?.role ?? null);
  const isAuthenticated = computed(() => user.value !== null);

  return { user, role, isAuthenticated, login, logout };
});
```

- [ ] **Step 4.2: 写 tests/unit/stores/auth.spec.ts**

```ts
import { describe, it, expect, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useAuthStore } from '@/stores/auth';
import type { User } from '@/types';

describe('useAuthStore', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it('初始未登录', () => {
    const s = useAuthStore();
    expect(s.user).toBeNull();
    expect(s.isAuthenticated).toBe(false);
    expect(s.role).toBeNull();
  });

  it('login 持久化到 localStorage', () => {
    const s = useAuthStore();
    const u: User = { id: 'u1', name: 'A', role: 'employee', department: 'D' };
    s.login(u);
    expect(s.user).toEqual(u);
    expect(s.role).toBe('employee');
    expect(s.isAuthenticated).toBe(true);
    expect(JSON.parse(localStorage.getItem('pp.auth.user')!)).toEqual(u);
  });

  it('logout 清空', () => {
    const s = useAuthStore();
    s.login({ id: 'u1', name: 'A', role: 'admin', department: 'D' });
    s.logout();
    expect(s.user).toBeNull();
    expect(localStorage.getItem('pp.auth.user')).toBeNull();
  });

  it('从 localStorage 恢复', () => {
    const u: User = { id: 'u2', name: 'B', role: 'admin', department: 'D' };
    localStorage.setItem('pp.auth.user', JSON.stringify(u));
    const s = useAuthStore();
    expect(s.user).toEqual(u);
  });
});
```

- [ ] **Step 4.3: 写 stores/project.ts**

```ts
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Project, ProjectStatus } from '@/types';

const KEY = 'pp.projects';

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>(loadProjects());
  const currentId = ref<string | null>(null);

  function loadProjects(): Project[] {
    if (typeof sessionStorage === 'undefined') return [];
    const raw = sessionStorage.getItem(KEY);
    try { return raw ? JSON.parse(raw) as Project[] : []; } catch { return []; }
  }

  function persist() {
    sessionStorage.setItem(KEY, JSON.stringify(projects.value));
  }

  function setAll(list: Project[]) {
    projects.value = list;
    persist();
  }

  function upsert(p: Project) {
    const idx = projects.value.findIndex(x => x.id === p.id);
    if (idx >= 0) projects.value[idx] = p;
    else projects.value.push(p);
    persist();
  }

  function setStatus(id: string, status: ProjectStatus) {
    const p = projects.value.find(x => x.id === id);
    if (!p) return;
    p.status = status;
    p.updatedAt = new Date().toISOString();
    persist();
  }

  function setCurrent(id: string | null) { currentId.value = id; }
  const current = computed(() =>
    projects.value.find(p => p.id === currentId.value) ?? null
  );

  function getById(id: string): Project | null {
    return projects.value.find(p => p.id === id) ?? null;
  }

  return { projects, currentId, current, setAll, upsert, setStatus, setCurrent, getById };
});
```

- [ ] **Step 4.4: 写 tests/unit/stores/project.spec.ts**

```ts
import { describe, it, expect, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useProjectStore } from '@/stores/project';
import type { Project } from '@/types';

const sample: Project = {
  id: 'p1', title: 't', domain: 'ai', description: 'd',
  status: 'drafting', ownerId: 'u1',
  createdAt: '2026-05-07T00:00:00Z', updatedAt: '2026-05-07T00:00:00Z',
};

describe('useProjectStore', () => {
  beforeEach(() => {
    sessionStorage.clear();
    setActivePinia(createPinia());
  });

  it('初始为空', () => {
    const s = useProjectStore();
    expect(s.projects).toEqual([]);
    expect(s.current).toBeNull();
  });

  it('upsert 新增并持久化', () => {
    const s = useProjectStore();
    s.upsert(sample);
    expect(s.projects).toHaveLength(1);
    expect(JSON.parse(sessionStorage.getItem('pp.projects')!)).toHaveLength(1);
  });

  it('upsert 同 id 覆盖', () => {
    const s = useProjectStore();
    s.upsert(sample);
    s.upsert({ ...sample, title: 't2' });
    expect(s.projects).toHaveLength(1);
    expect(s.projects[0].title).toBe('t2');
  });

  it('setStatus 更新状态与时间', () => {
    const s = useProjectStore();
    s.upsert(sample);
    const before = s.projects[0].updatedAt;
    s.setStatus('p1', 'submitted');
    expect(s.projects[0].status).toBe('submitted');
    expect(s.projects[0].updatedAt).not.toBe(before);
  });

  it('setCurrent + current computed 联动', () => {
    const s = useProjectStore();
    s.upsert(sample);
    s.setCurrent('p1');
    expect(s.current?.id).toBe('p1');
  });

  it('getById 找到/找不到', () => {
    const s = useProjectStore();
    s.upsert(sample);
    expect(s.getById('p1')?.id).toBe('p1');
    expect(s.getById('xxx')).toBeNull();
  });
});
```

- [ ] **Step 4.5: 写 stores/chat.ts**

```ts
import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { ChatMessage } from '@/types';

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([]);
  const streaming = ref(false);
  const capturedFields = ref<string[]>([]);

  function appendUser(content: string) {
    messages.value.push({
      id: `m-${Date.now()}-u`,
      role: 'user',
      content,
      ts: new Date().toISOString(),
    });
  }

  function startAgent() {
    messages.value.push({
      id: `m-${Date.now()}-a`,
      role: 'agent',
      content: '',
      ts: new Date().toISOString(),
    });
    streaming.value = true;
  }

  function appendDelta(chunk: string) {
    const last = messages.value[messages.value.length - 1];
    if (last && last.role === 'agent') {
      last.content += chunk;
    }
  }

  function applyFields(captured: string[]) {
    capturedFields.value = [...capturedFields.value, ...captured];
  }

  function endAgent() {
    streaming.value = false;
  }

  function reset() {
    messages.value = [];
    streaming.value = false;
    capturedFields.value = [];
  }

  return {
    messages, streaming, capturedFields,
    appendUser, startAgent, appendDelta, applyFields, endAgent, reset,
  };
});
```

- [ ] **Step 4.6: 写 tests/unit/stores/chat.spec.ts**

```ts
import { describe, it, expect, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useChatStore } from '@/stores/chat';

describe('useChatStore', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('appendUser 增加用户消息', () => {
    const s = useChatStore();
    s.appendUser('hi');
    expect(s.messages).toHaveLength(1);
    expect(s.messages[0].role).toBe('user');
    expect(s.messages[0].content).toBe('hi');
  });

  it('startAgent 增加空 agent 消息并标 streaming', () => {
    const s = useChatStore();
    s.startAgent();
    expect(s.messages).toHaveLength(1);
    expect(s.messages[0].role).toBe('agent');
    expect(s.messages[0].content).toBe('');
    expect(s.streaming).toBe(true);
  });

  it('appendDelta 累加到最后 agent 消息', () => {
    const s = useChatStore();
    s.startAgent();
    s.appendDelta('你');
    s.appendDelta('好');
    s.appendDelta('！');
    expect(s.messages[0].content).toBe('你好！');
  });

  it('applyFields 累计 captured', () => {
    const s = useChatStore();
    s.applyFields(['领域:AI']);
    s.applyFields(['问题:延迟']);
    expect(s.capturedFields).toEqual(['领域:AI', '问题:延迟']);
  });

  it('endAgent 切 streaming 为 false', () => {
    const s = useChatStore();
    s.startAgent();
    s.endAgent();
    expect(s.streaming).toBe(false);
  });

  it('reset 清空全部', () => {
    const s = useChatStore();
    s.appendUser('hi');
    s.applyFields(['x']);
    s.reset();
    expect(s.messages).toEqual([]);
    expect(s.streaming).toBe(false);
    expect(s.capturedFields).toEqual([]);
  });
});
```

- [ ] **Step 4.7: 写 stores/ui.ts**

```ts
import { defineStore } from 'pinia';
import { ref, watch } from 'vue';

const KEY = 'pp.ui';

interface UIState {
  theme: 'light' | 'dark';
  sidebarCollapsed: boolean;
}

function load(): UIState {
  if (typeof localStorage === 'undefined') return { theme: 'light', sidebarCollapsed: false };
  try { return JSON.parse(localStorage.getItem(KEY) ?? '') as UIState; }
  catch { return { theme: 'light', sidebarCollapsed: false }; }
}

export const useUIStore = defineStore('ui', () => {
  const initial = load();
  const theme = ref<'light' | 'dark'>(initial.theme);
  const sidebarCollapsed = ref(initial.sidebarCollapsed);

  function toggleTheme() { theme.value = theme.value === 'light' ? 'dark' : 'light'; }
  function toggleSidebar() { sidebarCollapsed.value = !sidebarCollapsed.value; }

  watch([theme, sidebarCollapsed], () => {
    localStorage.setItem(KEY, JSON.stringify({
      theme: theme.value,
      sidebarCollapsed: sidebarCollapsed.value,
    }));
  });

  return { theme, sidebarCollapsed, toggleTheme, toggleSidebar };
});
```

- [ ] **Step 4.8: 写 tests/unit/stores/ui.spec.ts**

```ts
import { describe, it, expect, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useUIStore } from '@/stores/ui';
import { nextTick } from 'vue';

describe('useUIStore', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it('默认 light + 不折叠', () => {
    const s = useUIStore();
    expect(s.theme).toBe('light');
    expect(s.sidebarCollapsed).toBe(false);
  });

  it('toggleTheme 切换并持久化', async () => {
    const s = useUIStore();
    s.toggleTheme();
    await nextTick();
    expect(s.theme).toBe('dark');
    const persisted = JSON.parse(localStorage.getItem('pp.ui')!);
    expect(persisted.theme).toBe('dark');
  });

  it('toggleSidebar 切换并持久化', async () => {
    const s = useUIStore();
    s.toggleSidebar();
    await nextTick();
    expect(s.sidebarCollapsed).toBe(true);
  });
});
```

- [ ] **Step 4.9: 跑测试**

```bash
cd frontend
pnpm test
```
Expected: 所有 store tests pass（22 tests 左右）。

- [ ] **Step 4.10: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/stores/ frontend/tests/unit/stores/
git commit -m "feat(frontend): add pinia stores (auth/project/chat/ui) with persistence

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5：SSE 消费器 utils/sse.ts + tests

**Files:**
- Create: `frontend/src/utils/sse.ts`
- Create: `frontend/tests/unit/utils/sse.spec.ts`

- [ ] **Step 5.1: 写 src/utils/sse.ts**

```ts
import type { ChatStreamEvent } from '@/types';

/** 用 fetch + ReadableStream 消费 SSE，逐事件回调。
 *  支持事件格式：`event: <type>\ndata: <json>\n\n`
 */
export async function consumeSSE(
  url: string,
  init: RequestInit,
  onEvent: (event: ChatStreamEvent) => void,
): Promise<void> {
  const res = await fetch(url, init);
  if (!res.body) throw new Error('SSE: response has no body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE event 以 \n\n 分隔
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';
    for (const block of events) {
      const ev = parseSSEBlock(block);
      if (ev) onEvent(ev);
    }
  }
}

function parseSSEBlock(block: string): ChatStreamEvent | null {
  const lines = block.split('\n').map(l => l.trim()).filter(Boolean);
  let type = '';
  let data = '';
  for (const line of lines) {
    if (line.startsWith('event:')) type = line.slice(6).trim();
    else if (line.startsWith('data:')) data = line.slice(5).trim();
  }
  if (!type) return null;
  if (type === 'thinking') return { type: 'thinking' };
  if (type === 'done') return { type: 'done' };
  let parsed: any = {};
  try { parsed = data ? JSON.parse(data) : {}; } catch { return null; }
  if (type === 'delta' && typeof parsed.chunk === 'string')
    return { type: 'delta', chunk: parsed.chunk };
  if (type === 'fields' && Array.isArray(parsed.captured))
    return { type: 'fields', captured: parsed.captured };
  return null;
}
```

- [ ] **Step 5.2: 写 tests/unit/utils/sse.spec.ts**

```ts
import { describe, it, expect, vi } from 'vitest';
import { consumeSSE } from '@/utils/sse';
import type { ChatStreamEvent } from '@/types';

function makeStreamingResponse(chunks: string[]): Response {
  const stream = new ReadableStream({
    start(controller) {
      const enc = new TextEncoder();
      for (const c of chunks) controller.enqueue(enc.encode(c));
      controller.close();
    }
  });
  return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } });
}

describe('consumeSSE', () => {
  it('解析 thinking + delta + fields + done', async () => {
    const sseText =
      'event: thinking\ndata: {}\n\n' +
      'event: delta\ndata: {"chunk":"你好"}\n\n' +
      'event: fields\ndata: {"captured":["领域:AI"]}\n\n' +
      'event: done\ndata: {}\n\n';

    const fetchSpy = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValue(makeStreamingResponse([sseText]));

    const events: ChatStreamEvent[] = [];
    await consumeSSE('/api/test', { method: 'POST' }, e => events.push(e));

    expect(events).toEqual([
      { type: 'thinking' },
      { type: 'delta', chunk: '你好' },
      { type: 'fields', captured: ['领域:AI'] },
      { type: 'done' },
    ]);
    fetchSpy.mockRestore();
  });

  it('支持事件跨 chunk 边界', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      makeStreamingResponse([
        'event: delta\ndata: {"chu',
        'nk":"片段"}\n\n',
        'event: done\ndata: {}\n\n',
      ])
    );
    const events: ChatStreamEvent[] = [];
    await consumeSSE('/api/test', { method: 'POST' }, e => events.push(e));
    expect(events).toEqual([
      { type: 'delta', chunk: '片段' },
      { type: 'done' },
    ]);
    fetchSpy.mockRestore();
  });

  it('未知事件类型被忽略', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      makeStreamingResponse(['event: weird\ndata: {}\n\n'])
    );
    const events: ChatStreamEvent[] = [];
    await consumeSSE('/api/test', { method: 'POST' }, e => events.push(e));
    expect(events).toEqual([]);
    fetchSpy.mockRestore();
  });
});
```

- [ ] **Step 5.3: 跑测试**

```bash
cd frontend
pnpm test
```
Expected: 3 tests pass（合计现在 ~25 tests）。

- [ ] **Step 5.4: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/utils/sse.ts frontend/tests/unit/utils/sse.spec.ts
git commit -m "feat(frontend): add SSE consumer with cross-chunk parsing

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6：Mock fixtures（users + 3 个 demo case）

**Files:**
- Create: `frontend/src/mock/fixtures/users.ts`
- Create: `frontend/src/mock/fixtures/case_crypto.ts`
- Create: `frontend/src/mock/fixtures/case_infosec.ts`
- Create: `frontend/src/mock/fixtures/case_ai.ts`
- Create: `frontend/src/mock/fixtures/all_cases.ts`

> 三个 case 数据量大但属于"内容工程"——结构相同，只填字段。下面给 case_crypto 完整模板，case_infosec 与 case_ai 按相同结构填写各自内容。

- [ ] **Step 6.1: 写 fixtures/users.ts**

```ts
import type { User } from '@/types';

export const DEMO_USERS: User[] = [
  { id: 'u1', name: '张工程师', role: 'employee', department: '研发-AI 平台部' },
  { id: 'u2', name: '王管理员', role: 'admin',    department: 'IP 总部' },
];

export const DEFAULT_EMPLOYEE = DEMO_USERS[0];
export const DEFAULT_ADMIN = DEMO_USERS[1];
```

- [ ] **Step 6.2: 写 fixtures/case_crypto.ts（密码学 case · submitted）**

```ts
import type { Project, ChatMessage, PriorArtHit } from '@/types';

const conversation: ChatMessage[] = [
  { id: 'c1-a1', role: 'agent', ts: '2026-05-01T09:00:00Z',
    content: '欢迎报门！你提到对 Kyber-512 NTT 做了优化，我先确认下你说的"通道并行"是指 SIMD 向量化、还是多线程并行、还是别的？',
    meta: { stage: '5why', capturedFields: ['领域:后量子密码', '领域:Kyber-512'] } },
  { id: 'c1-u1', role: 'user', ts: '2026-05-01T09:01:00Z',
    content: '主要是 ARM Cortex-M4 的 SIMD 向量化，把 NTT 的蝶形运算两路并行做。' },
  { id: 'c1-a2', role: 'agent', ts: '2026-05-01T09:02:00Z',
    content: '理解。那 NTT 的优化对其他子模块（Compression / SHAKE）有联动改动吗？还是只动 NTT？',
    meta: { stage: '5why', capturedFields: ['手段:SIMD 向量化', '手段:蝶形并行'] } },
  { id: 'c1-u2', role: 'user', ts: '2026-05-01T09:03:00Z',
    content: '只动 NTT。Compression 和 SHAKE 没动。' },
  { id: 'c1-a3', role: 'agent', ts: '2026-05-01T09:04:00Z',
    content: '好的。性能上 38% 提升是相对什么基线？是 PQClean 的标量参考实现，还是 pqm4 的优化版？',
    meta: { stage: 'whatif', capturedFields: ['区别:相对 baseline'] } },
  { id: 'c1-u3', role: 'user', ts: '2026-05-01T09:05:00Z',
    content: '相对 PQClean 标量参考。pqm4 我们还没系统对比。' },
  { id: 'c1-a4', role: 'agent', ts: '2026-05-01T09:06:00Z',
    content: '建议补充 pqm4 对比，否则审查员可能用 pqm4 当 D1。除了速度，能耗或代码体积有变化吗？',
    meta: { stage: 'effect', capturedFields: ['效果:速度+38%'] } },
  { id: 'c1-u4', role: 'user', ts: '2026-05-01T09:07:00Z',
    content: '代码体积增加约 1.8KB，能耗暂未测。' },
  { id: 'c1-a5', role: 'agent', ts: '2026-05-01T09:08:00Z',
    content: '差不多够了。结构化要素已捕获完整，可以进入检索环节。建议你之后补 pqm4 对比与能耗测试以支撑创造性论证。',
    meta: { stage: 'generalize', capturedFields: ['效果:体积+1.8KB'] } },
];

const hits: PriorArtHit[] = [
  { id: 'CN114444128A', title: '一种基于格密码的密钥封装方法', applicant: '中国电信',
    pubDate: '2022-05-06', ipc: ['H04L 9/30'], xyn: 'Y',
    abstract: '一种基于 Kyber 框架的密钥封装方法，对 NTT 进行标量优化…（演示数据）',
    comparison: { problem: '类似', means: '标量优化 vs 本案 SIMD 向量化', effect: '提升 12%' } },
  { id: 'EP3863215A1', title: 'Optimized NTT for lattice-based KEM', applicant: 'Infineon',
    pubDate: '2021-08-11', ipc: ['H04L 9/30'], xyn: 'Y',
    abstract: 'NTT acceleration via word-level parallelism on 32-bit ARM cores…（演示数据）',
    comparison: { problem: '相同', means: 'word-level 并行', effect: '提升 22%' } },
  { id: 'arXiv:2110.10377', title: 'Faster Kyber on Cortex-M4', applicant: 'CHES paper',
    pubDate: '2021-10-20', ipc: [], xyn: 'Y',
    abstract: '对 pqm4 的 Cortex-M4 Kyber 进一步内联汇编优化…（演示数据）',
    comparison: { problem: '相同', means: '内联汇编优化', effect: '提升 18%' } },
  { id: 'CN115021899A', title: '抗量子密钥协商方法', applicant: '华为',
    pubDate: '2022-09-09', ipc: ['H04L 9/30'], xyn: 'N',
    abstract: '一种基于 Kyber 与 Falcon 混合的协商协议…（演示数据）',
    comparison: { problem: '不相关（协议层）', means: '混合协议', effect: '安全性提升' } },
  { id: 'CN116112184A', title: '面向嵌入式的 SHA3 加速', applicant: '紫光',
    pubDate: '2023-04-04', ipc: ['H04L 9/06'], xyn: 'N',
    abstract: 'SHA3 KECCAK 在 Cortex-M 的加速实现…（演示数据）',
    comparison: { problem: '不相关', means: 'SHA3 加速', effect: '不相关' } },
  { id: 'US2022/0150047', title: 'Lattice-based crypto on FPGA', applicant: 'IBM',
    pubDate: '2022-05-12', ipc: ['H04L 9/30'], xyn: 'N',
    abstract: 'FPGA 上的格密码加速…（演示数据）',
    comparison: { problem: '硬件平台不同', means: 'FPGA', effect: '硬件加速' } },
  { id: 'CN114172627A', title: '一种 LWE 加密方法', applicant: '清华大学',
    pubDate: '2022-03-01', ipc: ['H04L 9/30'], xyn: 'N',
    abstract: '基于 LWE 的加密方法…（演示数据）',
    comparison: { problem: '范畴不同', means: 'LWE 通用方法', effect: '通用' } },
  { id: 'CN116232544A', title: '后量子签名优化', applicant: '中科院',
    pubDate: '2023-06-06', ipc: ['H04L 9/32'], xyn: 'N',
    abstract: 'Falcon 签名在嵌入式平台的实现…（演示数据）',
    comparison: { problem: '签名不是 KEM', means: 'Falcon 签名', effect: '不相关' } },
];

export const CASE_CRYPTO: Project = {
  id: 'p-crypto-001',
  title: '一种基于 Kyber-512 NTT 并行优化的轻量级 PQC KEM 实现',
  domain: 'cryptography',
  description: 'NIST 后量子标准 Kyber 的 NTT 子运算做了通道并行+向量化，嵌入式 ARM Cortex-M4 上密钥封装快了 38%。相对 PQClean 标量参考实现 38% 提升，代码体积增加 1.8KB。',
  status: 'submitted',
  ownerId: 'u1',
  createdAt: '2026-05-01T09:00:00Z',
  updatedAt: '2026-05-04T15:30:00Z',
  miningSummary: {
    field: ['后量子密码', 'Kyber-512', 'NTT', 'ARM Cortex-M4'],
    problem: ['NTT 在嵌入式平台速度瓶颈', 'PQClean 标量实现性能不足'],
    means: ['SIMD 向量化', 'NTT 蝶形运算两路并行', '32-bit word 通道并行'],
    effect: ['密钥封装快 38%', '代码体积 +1.8KB'],
    differentiator: ['只动 NTT 不联动其他子模块', '相对 PQClean 标量基线'],
    conversation,
  },
  searchReport: {
    patentability: 'moderate',
    rationale: '本申请相对 PQClean 标量参考实现有 38% 提升，但 EP3863215A1（Infineon, word-level 并行）与本案手段有相似处。建议补充 pqm4 与 word-level 并行的对比实验，论证 SIMD 向量化的非显而易见性。',
    hits,
  },
  disclosure: {
    technicalField: '本发明涉及后量子密码学领域，特别涉及一种针对 Kyber-512 KEM 算法在嵌入式 ARM Cortex-M4 平台上的 NTT 并行优化实现方法。',
    background: '现有 Kyber-512 在 PQClean 中提供的标量参考实现，由于未充分利用 ARM 处理器的 SIMD 能力，导致在资源受限的物联网设备上密钥封装/解封装耗时较长，难以满足实时通信需求…',
    summary: '本发明提供一种基于 Kyber-512 NTT 并行优化的轻量级 PQC KEM 实现方法，通过对 NTT 蝶形运算的两路 SIMD 向量化，使密钥封装速度相对 PQClean 标量参考提升 38%，代码体积仅增加 1.8KB。',
    claims: [
      { tier: 'broad', text: '一种 Kyber-512 KEM 实现方法，其特征在于对 NTT 子运算进行向量化并行处理。',
        risk: '上位过激，可能被 EP3863215A1 word-level 并行破创造性' },
      { tier: 'medium', text: '一种 Kyber-512 KEM 实现方法，包括：在 ARM Cortex-M4 上对 NTT 蝶形运算执行 SIMD 两路并行；保持 Compression 和 SHAKE 子模块不变；其特征在于密钥封装速度相对标量参考提升至少 30%。',
        risk: '稳妥' },
      { tier: 'narrow', text: '一种 Kyber-512 KEM 实现方法，限定 SIMD 通道宽度为 32-bit、并行路数为 2、目标平台为 ARM Cortex-M4，相对 PQClean v1.x 提升 38%、代码体积增量 1.8KB。',
        risk: '紧贴实施例，确定性高' },
    ],
    drawingsDescription: '图 1 为系统架构示意图；图 2 为 NTT 并行流水线；图 3 为性能对比柱状图。',
    embodiments: '实施例 1：在 STM32L4 上集成本方法，与 PQClean 1.0.0 对比，密钥封装从 12.4ms 降至 7.7ms（38% 提升）。代码体积由 18.2KB 增加到 20.0KB。…',
    bodyMarkdown: '',
  },
};
```

- [ ] **Step 6.3: 写 fixtures/case_infosec.ts（信息安全 case · submitted · strong）**

按 case_crypto.ts 同结构编写：
- title: '一种基于多信号融合行为基线的 API 网关异常请求检测方法与系统'
- domain: 'infosec'
- status: 'submitted'
- patentability: 'strong'
- 5 轮对话内容围绕 z-score / GBDT / 滑动窗口 自适应阈值
- 8 篇 hits：0 X / 2 Y / 6 N（Y: z-score 单一信号、GBDT 用户分类）
- 三档独权
- claim broad: 一种 API 网关异常请求检测方法（仅多信号融合）
- claim medium: 增加 z-score+GBDT+滑动窗口三路组合 + 决策融合
- claim narrow: 限定 z-score 阈值算法、GBDT 特征工程明细、滑动窗口 5min/30min 双窗
- rationale: '在 z-score 单一信号 + GBDT 单分类基础上，本案的多信号决策融合 + 自适应阈值无现有技术覆盖，新颖性创造性都强。'

> 实施时按 case_crypto.ts 模板填充，确保 8 个 hit、5 轮对话、3 档 claim 完整存在；公开号选真实存在的（避免不可验证）。完整文本参考 spec §5。

- [ ] **Step 6.4: 写 fixtures/case_ai.ts（AI case · drafting · weak）**

按 case_crypto.ts 同结构编写：
- title: '一种基于 KV-cache 分页与请求级动态调度的大模型推理批处理方法'
- domain: 'ai'
- status: 'drafting'
- patentability: 'weak'
- 5 轮对话最后一轮 agent 明确建议"vLLM 已公开此核心思路，建议聚焦到非首推用户场景的优先级调度"
- 8 篇 hits：**2 X**（vLLM PagedAttention 论文 arXiv:2309.06180、CN 同等申请）/ 3 Y / 3 N
- 三档独权 + risk 标注突出"被 vLLM 击破新颖性"
- rationale: 'vLLM PagedAttention（SOSP 2023）已公开 KV-cache 分页核心思想，作为独权将被 X 类破新颖。建议本申请缩窄到具体的非首推用户优先级调度策略，或本人放弃申请。'

> 实施时同 §5 spec 内容填充。这个 case 的 disclosure 要保留（员工已写完才决定不交），bodyMarkdown 可有内容。

- [ ] **Step 6.5: 写 fixtures/all_cases.ts**

```ts
import type { Project } from '@/types';
import { CASE_CRYPTO } from './case_crypto';
import { CASE_INFOSEC } from './case_infosec';
import { CASE_AI } from './case_ai';

export const ALL_CASES: Project[] = [CASE_CRYPTO, CASE_INFOSEC, CASE_AI];

export function findCase(id: string): Project | undefined {
  return ALL_CASES.find(p => p.id === id);
}

/** 给某 case 取第 n 轮 agent 答复（用于 chat handler）。round 从 1 起 */
export function getCaseAgentScript(projectId: string, round: number): {
  text: string; capturedFields: string[];
} | null {
  const p = findCase(projectId);
  if (!p?.miningSummary) return null;
  const agentMsgs = p.miningSummary.conversation.filter(m => m.role === 'agent');
  const msg = agentMsgs[round - 1];
  if (!msg) return null;
  return {
    text: msg.content,
    capturedFields: msg.meta?.capturedFields ?? [],
  };
}
```

- [ ] **Step 6.6: 跑现有测试看 fixtures import 不破坏其他东西**

```bash
cd frontend
pnpm test
```
Expected: 全绿（不引入新 test，仅确保编译过）。

- [ ] **Step 6.7: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/mock/fixtures/
git commit -m "feat(frontend): add 3 demo case fixtures (crypto/infosec/ai) + users

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7：API client + handlers（auth/projects/search/disclosure）+ tests

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/auth.ts` `frontend/src/api/projects.ts` `frontend/src/api/search.ts` `frontend/src/api/disclosure.ts`
- Create: `frontend/src/mock/handlers/auth.ts` `projects.ts` `search.ts` `disclosure.ts`
- Modify: `frontend/src/mock/handlers/index.ts`
- Create: `frontend/tests/unit/mock/handlers/projects.spec.ts`

- [ ] **Step 7.1: 写 src/api/client.ts**

```ts
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
```

- [ ] **Step 7.2: 写 src/api/auth.ts**

```ts
import { apiClient } from './client';
import type { User, Role } from '@/types';

export const authApi = {
  loginAs: (role: Role) =>
    apiClient.post<User>('/auth/login-as', { role }).then(r => r.data),
  me: () => apiClient.get<User>('/auth/me').then(r => r.data),
};
```

- [ ] **Step 7.3: 写 src/api/projects.ts**

```ts
import { apiClient } from './client';
import type { Project, Domain } from '@/types';

export const projectsApi = {
  list: (params?: { ownerId?: string }) =>
    apiClient.get<Project[]>('/projects', { params }).then(r => r.data),
  get: (id: string) =>
    apiClient.get<Project>(`/projects/${id}`).then(r => r.data),
  create: (data: { title: string; description: string; domain: Domain; ownerId: string }) =>
    apiClient.post<Project>('/projects', data).then(r => r.data),
  submit: (id: string) =>
    apiClient.post<Project>(`/projects/${id}/submit`).then(r => r.data),
  unsubmit: (id: string) =>
    apiClient.post<Project>(`/projects/${id}/unsubmit`).then(r => r.data),
};
```

- [ ] **Step 7.4: 写 src/api/search.ts**

```ts
import { apiClient } from './client';
import type { SearchReport } from '@/types';

export const searchApi = {
  run: (projectId: string) =>
    apiClient.post<SearchReport>(`/projects/${projectId}/search`).then(r => r.data),
};
```

- [ ] **Step 7.5: 写 src/api/disclosure.ts**

```ts
import { apiClient } from './client';
import type { Disclosure, ClaimTier } from '@/types';

export const disclosureApi = {
  get: (projectId: string) =>
    apiClient.get<Disclosure>(`/projects/${projectId}/disclosure`).then(r => r.data),
  save: (projectId: string, body: Partial<Disclosure>) =>
    apiClient.put<Disclosure>(`/projects/${projectId}/disclosure`, body).then(r => r.data),
  selectClaimTier: (projectId: string, tier: ClaimTier) =>
    apiClient.post<Disclosure>(`/projects/${projectId}/disclosure/claim-tier`, { tier }).then(r => r.data),
};
```

- [ ] **Step 7.6: 写 mock/handlers/auth.ts**

```ts
import { http, HttpResponse } from 'msw';
import type { Role } from '@/types';
import { DEMO_USERS } from '../fixtures/users';

export const authHandlers = [
  http.post('/api/auth/login-as', async ({ request }) => {
    const { role } = await request.json() as { role: Role };
    const user = DEMO_USERS.find(u => u.role === role);
    if (!user) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json(user);
  }),
];
```

- [ ] **Step 7.7: 写 mock/handlers/projects.ts**

```ts
import { http, HttpResponse } from 'msw';
import type { Project, Domain } from '@/types';
import { ALL_CASES, findCase } from '../fixtures/all_cases';

// 内存中可变项目仓（基于 ALL_CASES 拷贝，演示用）
const store: Project[] = JSON.parse(JSON.stringify(ALL_CASES));

export const projectsHandlers = [
  http.get('/api/projects', ({ request }) => {
    const url = new URL(request.url);
    const ownerId = url.searchParams.get('ownerId');
    const list = ownerId ? store.filter(p => p.ownerId === ownerId) : store;
    return HttpResponse.json(list);
  }),

  http.get('/api/projects/:id', ({ params }) => {
    const p = store.find(x => x.id === params.id);
    return p ? HttpResponse.json(p) : new HttpResponse(null, { status: 404 });
  }),

  http.post('/api/projects', async ({ request }) => {
    const body = await request.json() as {
      title: string; description: string; domain: Domain; ownerId: string;
    };
    const newP: Project = {
      id: `p-new-${Date.now()}`,
      title: body.title,
      description: body.description,
      domain: body.domain,
      ownerId: body.ownerId,
      status: 'drafting',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    store.push(newP);
    return HttpResponse.json(newP, { status: 201 });
  }),

  http.post('/api/projects/:id/submit', ({ params }) => {
    const p = store.find(x => x.id === params.id);
    if (!p) return new HttpResponse(null, { status: 404 });
    p.status = 'submitted';
    p.updatedAt = new Date().toISOString();
    return HttpResponse.json(p);
  }),

  http.post('/api/projects/:id/unsubmit', ({ params }) => {
    const p = store.find(x => x.id === params.id);
    if (!p) return new HttpResponse(null, { status: 404 });
    p.status = 'reporting';
    p.updatedAt = new Date().toISOString();
    return HttpResponse.json(p);
  }),
];
```

- [ ] **Step 7.8: 写 mock/handlers/search.ts**

```ts
import { http, HttpResponse } from 'msw';
import { findCase } from '../fixtures/all_cases';
import { sleep } from '../utils';

export const searchHandlers = [
  http.post('/api/projects/:id/search', async ({ params }) => {
    await sleep(800); // 模拟检索耗时
    const p = findCase(params.id as string);
    if (!p?.searchReport) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json(p.searchReport);
  }),
];
```

- [ ] **Step 7.9: 写 mock/handlers/disclosure.ts**

```ts
import { http, HttpResponse } from 'msw';
import type { Disclosure, ClaimTier } from '@/types';
import { findCase } from '../fixtures/all_cases';

export const disclosureHandlers = [
  http.get('/api/projects/:id/disclosure', ({ params }) => {
    const p = findCase(params.id as string);
    return p?.disclosure
      ? HttpResponse.json(p.disclosure)
      : new HttpResponse(null, { status: 404 });
  }),

  http.put('/api/projects/:id/disclosure', async ({ params, request }) => {
    const body = await request.json() as Partial<Disclosure>;
    const p = findCase(params.id as string);
    if (!p?.disclosure) return new HttpResponse(null, { status: 404 });
    Object.assign(p.disclosure, body);
    return HttpResponse.json(p.disclosure);
  }),

  http.post('/api/projects/:id/disclosure/claim-tier', async ({ params, request }) => {
    const { tier } = await request.json() as { tier: ClaimTier };
    const p = findCase(params.id as string);
    if (!p?.disclosure) return new HttpResponse(null, { status: 404 });
    // mock 行为：把 summary 段重写为对应档（实际代码可以更聪明，这里简单演示）
    const claim = p.disclosure.claims.find(c => c.tier === tier);
    if (claim) {
      p.disclosure.summary = `[已选择${tier}档] ${claim.text}`;
    }
    return HttpResponse.json(p.disclosure);
  }),
];
```

- [ ] **Step 7.10: 修改 mock/handlers/index.ts**

```ts
import { http, HttpResponse } from 'msw';
import { authHandlers } from './auth';
import { projectsHandlers } from './projects';
import { searchHandlers } from './search';
import { disclosureHandlers } from './disclosure';

export const handlers = [
  http.get('/api/ping', () => HttpResponse.json({ ok: true, msg: 'msw working' })),
  ...authHandlers,
  ...projectsHandlers,
  ...searchHandlers,
  ...disclosureHandlers,
];
```

- [ ] **Step 7.11: 写 tests/unit/mock/handlers/projects.spec.ts**

```ts
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { handlers } from '@/mock/handlers';
import { projectsApi } from '@/api/projects';

const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('projects mock handlers', () => {
  it('GET /projects 返回 3 个 demo case', async () => {
    const list = await projectsApi.list();
    expect(list).toHaveLength(3);
  });

  it('GET /projects/:id 拿到密码学 case', async () => {
    const p = await projectsApi.get('p-crypto-001');
    expect(p.title).toContain('Kyber');
  });

  it('POST /projects 创建新项目并默认 drafting', async () => {
    const p = await projectsApi.create({
      title: '测试', description: 'd', domain: 'other', ownerId: 'u1',
    });
    expect(p.status).toBe('drafting');
    expect(p.id).toMatch(/^p-new-/);
  });

  it('POST /projects/:id/submit 改状态为 submitted', async () => {
    const p = await projectsApi.submit('p-crypto-001');
    expect(p.status).toBe('submitted');
  });

  it('POST /projects/:id/unsubmit 改状态回 reporting', async () => {
    const p = await projectsApi.unsubmit('p-crypto-001');
    expect(p.status).toBe('reporting');
  });
});
```

- [ ] **Step 7.12: 跑测试**

```bash
cd frontend
pnpm test
```
Expected: 5 个新 test 全过；之前 ~25 也都过。

- [ ] **Step 7.13: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/api/ frontend/src/mock/handlers/ frontend/tests/unit/mock/
git commit -m "feat(frontend): API client + MSW handlers (auth/projects/search/disclosure)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8：Chat handler · SSE 伪流式 + tests

**Files:**
- Create: `frontend/src/api/chat.ts`
- Create: `frontend/src/mock/handlers/chat.ts`
- Modify: `frontend/src/mock/handlers/index.ts`
- Create: `frontend/tests/unit/mock/handlers/chat.spec.ts`

- [ ] **Step 8.1: 写 src/api/chat.ts**

```ts
import type { ChatStreamEvent } from '@/types';
import { consumeSSE } from '@/utils/sse';

export const chatApi = {
  /** 发一轮对话，回调每个 SSE 事件 */
  stream(projectId: string, round: number, userMsg: string,
         onEvent: (e: ChatStreamEvent) => void): Promise<void> {
    return consumeSSE(`/api/projects/${projectId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ round, userMsg }),
    }, onEvent);
  },
};
```

- [ ] **Step 8.2: 写 src/mock/handlers/chat.ts**

```ts
import { http, HttpResponse } from 'msw';
import { getCaseAgentScript } from '../fixtures/all_cases';
import { sleep, splitByGrapheme, rand } from '../utils';

export const chatHandlers = [
  http.post('/api/projects/:id/chat', async ({ params, request }) => {
    const { round } = await request.json() as { round: number; userMsg: string };
    const script = getCaseAgentScript(params.id as string, round);

    const stream = new ReadableStream({
      async start(controller) {
        const encoder = new TextEncoder();

        // 1. thinking 信号
        controller.enqueue(encoder.encode('event: thinking\ndata: {}\n\n'));
        await sleep(400);

        // 2. 没有 script 时返回兜底答复
        const text = script?.text
          ?? '抱歉，我没找到对应的预设答复（演示数据未覆盖此轮）。可以让员工继续描述。';

        // 3. 按 grapheme 切 chunk，每 chunk 25-60ms 释放
        for (const chunk of splitByGrapheme(text, 3)) {
          controller.enqueue(encoder.encode(
            `event: delta\ndata: ${JSON.stringify({ chunk })}\n\n`,
          ));
          await sleep(rand(25, 60));
        }

        // 4. 字段更新事件
        controller.enqueue(encoder.encode(
          `event: fields\ndata: ${JSON.stringify({ captured: script?.capturedFields ?? [] })}\n\n`,
        ));

        // 5. done
        controller.enqueue(encoder.encode('event: done\ndata: {}\n\n'));
        controller.close();
      },
    });

    return new HttpResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
    });
  }),
];
```

- [ ] **Step 8.3: 修改 mock/handlers/index.ts 加 chatHandlers**

```ts
import { http, HttpResponse } from 'msw';
import { authHandlers } from './auth';
import { projectsHandlers } from './projects';
import { searchHandlers } from './search';
import { disclosureHandlers } from './disclosure';
import { chatHandlers } from './chat';

export const handlers = [
  http.get('/api/ping', () => HttpResponse.json({ ok: true, msg: 'msw working' })),
  ...authHandlers,
  ...projectsHandlers,
  ...searchHandlers,
  ...disclosureHandlers,
  ...chatHandlers,
];
```

- [ ] **Step 8.4: 写 tests/unit/mock/handlers/chat.spec.ts**

```ts
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { handlers } from '@/mock/handlers';
import { chatApi } from '@/api/chat';
import type { ChatStreamEvent } from '@/types';

const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('chat SSE handler', () => {
  it('密码学 case 第 1 轮：流式吐出 thinking + delta * N + fields + done', async () => {
    const events: ChatStreamEvent[] = [];
    await chatApi.stream('p-crypto-001', 1, 'hi', e => events.push(e));

    expect(events[0]).toEqual({ type: 'thinking' });
    expect(events[events.length - 1]).toEqual({ type: 'done' });

    const fieldsEvent = events.find(e => e.type === 'fields');
    expect(fieldsEvent).toBeDefined();
    if (fieldsEvent?.type === 'fields') {
      expect(fieldsEvent.captured).toEqual(
        expect.arrayContaining(['领域:后量子密码', '领域:Kyber-512']),
      );
    }

    const deltas = events.filter(e => e.type === 'delta');
    expect(deltas.length).toBeGreaterThan(5); // 至少 6 个 chunk
    const fullText = deltas.map(d => d.type === 'delta' ? d.chunk : '').join('');
    expect(fullText).toContain('Kyber-512');
  }, 15_000);

  it('未知 round 返回兜底', async () => {
    const events: ChatStreamEvent[] = [];
    await chatApi.stream('p-crypto-001', 999, 'hi', e => events.push(e));
    const deltas = events.filter(e => e.type === 'delta');
    const fullText = deltas.map(d => d.type === 'delta' ? d.chunk : '').join('');
    expect(fullText).toContain('演示数据未覆盖');
  }, 15_000);
});
```

- [ ] **Step 8.5: 跑测试**

```bash
cd frontend
pnpm test
```
Expected: 2 个 chat tests 通过（含 SSE 流式解析）；总测试约 30+。

- [ ] **Step 8.6: 浏览器手动验证流式（可选 sanity check）**

```bash
pnpm dev
```
打开 DevTools → Network。手动用 curl 不行（SSE 走 service worker），用页面发请求暂未实现，跳过——Task 12 在 ProjectMining 页接通后会自然验证。

- [ ] **Step 8.7: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/api/chat.ts frontend/src/mock/handlers/chat.ts frontend/src/mock/handlers/index.ts frontend/tests/unit/mock/handlers/chat.spec.ts
git commit -m "feat(frontend): SSE-based pseudo-streaming chat mock handler

按 grapheme 切 chunk、25-60ms 抖动、event 序列：thinking → delta* → fields → done

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9：路由 + RBAC 守卫 + tests

**Files:**
- Create: `frontend/src/router/routes.ts`
- Create: `frontend/src/router/guards.ts`
- Create: `frontend/src/router/index.ts`
- Modify: `frontend/src/main.ts`
- Create: `frontend/tests/unit/router/guards.spec.ts`

- [ ] **Step 9.1: 写 src/router/routes.ts**

```ts
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
      { path: 'projects/:id/mining', name: 'project-mining',
        component: () => import('@/views/employee/ProjectMining.vue').catch(() => Empty()) },
      { path: 'projects/:id/search', name: 'project-search',
        component: () => import('@/views/employee/ProjectSearch.vue').catch(() => Empty()) },
      { path: 'projects/:id/disclosure', name: 'project-disclosure',
        component: () => import('@/views/employee/ProjectDisclosure.vue').catch(() => Empty()) },
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
```

- [ ] **Step 9.2: 写 src/router/guards.ts**

```ts
import type { Router } from 'vue-router';
import type { Role } from '@/types';
import { useAuthStore } from '@/stores/auth';

export function setupGuards(router: Router) {
  router.beforeEach((to) => {
    const auth = useAuthStore();
    const path = to.path;

    // 公共
    if (path === '/login' || path === '/403' || path === '/not-found') return true;

    // 未登录 → 登录
    if (!auth.isAuthenticated) return { path: '/login' };

    // 角色检查
    const allowedRoles = (to.matched
      .flatMap(r => (r.meta?.roles as Role[] | undefined) ?? []));

    if (allowedRoles.length === 0) return true; // 无要求
    if (auth.role && allowedRoles.includes(auth.role)) return true;

    return { path: '/403' };
  });
}
```

- [ ] **Step 9.3: 写 src/router/index.ts**

```ts
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
```

- [ ] **Step 9.4: 修改 src/main.ts 接入 router**

```ts
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
```

- [ ] **Step 9.5: 写 tests/unit/router/guards.spec.ts**

```ts
import { describe, it, expect, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';
import { setupGuards } from '@/router/guards';
import { useAuthStore } from '@/stores/auth';
import type { User } from '@/types';

const employee: User = { id: 'u1', name: 'A', role: 'employee', department: 'D' };
const admin: User = { id: 'u2', name: 'B', role: 'admin', department: 'D' };

function makeRouter() {
  const r = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', redirect: '/login' },
      { path: '/login', component: { template: '<div/>' } },
      { path: '/403', component: { template: '<div/>' } },
      { path: '/employee/x', component: { template: '<div/>' }, meta: { roles: ['employee', 'admin'] } },
      { path: '/admin/x', component: { template: '<div/>' }, meta: { roles: ['admin'] } },
    ],
  });
  setupGuards(r);
  return r;
}

describe('RBAC guards', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it('未登录访问受保护路径跳 login', async () => {
    const r = makeRouter();
    await r.push('/admin/x');
    expect(r.currentRoute.value.path).toBe('/login');
  });

  it('登录后访问允许的路径成功', async () => {
    const r = makeRouter();
    useAuthStore().login(employee);
    await r.push('/employee/x');
    expect(r.currentRoute.value.path).toBe('/employee/x');
  });

  it('员工访问 admin 路径 → 403', async () => {
    const r = makeRouter();
    useAuthStore().login(employee);
    await r.push('/admin/x');
    expect(r.currentRoute.value.path).toBe('/403');
  });

  it('admin 访问员工路径成功（兼具浏览权）', async () => {
    const r = makeRouter();
    useAuthStore().login(admin);
    await r.push('/employee/x');
    expect(r.currentRoute.value.path).toBe('/employee/x');
  });
});
```

- [ ] **Step 9.6: 写最简 src/components/common/Empty.vue（被 routes 兜底用）**

```vue
<script setup lang="ts">
import { useRoute } from 'vue-router';
const route = useRoute();
</script>
<template>
  <div style="padding:48px;text-align:center;color:#888;font-family:monospace">
    [Empty placeholder] {{ route.fullPath }}
  </div>
</template>
```

- [ ] **Step 9.7: 跑测试**

```bash
cd frontend
pnpm test
```
Expected: 4 个新 router tests 通过；总 ~34 tests pass。

- [ ] **Step 9.8: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/router/ frontend/src/components/common/Empty.vue frontend/src/main.ts frontend/tests/unit/router/
git commit -m "feat(frontend): vue-router with RBAC guards (employee/admin)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10：Layouts + 通用组件（RoleBadge / ReadonlyBanner）

**Files:**
- Create: `frontend/src/layouts/DefaultLayout.vue`
- Create: `frontend/src/layouts/BlankLayout.vue`
- Create: `frontend/src/components/common/RoleBadge.vue`
- Create: `frontend/src/components/common/ReadonlyBanner.vue`

- [ ] **Step 10.1: 写 layouts/BlankLayout.vue**

```vue
<script setup lang="ts">
</script>
<template>
  <div style="min-height:100vh; background: var(--pp-bg);">
    <router-view />
  </div>
</template>
```

- [ ] **Step 10.2: 写 components/common/RoleBadge.vue**

```vue
<script setup lang="ts">
import { computed } from 'vue';
import type { Role } from '@/types';

const props = defineProps<{ role: Role | null }>();
const text = computed(() => props.role === 'admin' ? '管理员' : props.role === 'employee' ? '员工' : '未登录');
const color = computed(() => props.role === 'admin' ? 'gold' : props.role === 'employee' ? 'blue' : 'default');
</script>
<template>
  <a-tag :color="color" style="margin-left:8px">{{ text }}</a-tag>
</template>
```

- [ ] **Step 10.3: 写 components/common/ReadonlyBanner.vue**

```vue
<script setup lang="ts">
defineProps<{ show: boolean }>();
</script>
<template>
  <a-alert v-if="show" type="warning" show-icon banner
           message="只读模式 (admin 视角)"
           description="您正在以管理员身份查看员工项目，所有编辑/提交按钮已隐藏。" />
</template>
```

- [ ] **Step 10.4: 写 layouts/DefaultLayout.vue（含侧栏 + 顶栏）**

```vue
<script setup lang="ts">
import { computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useUIStore } from '@/stores/ui';
import RoleBadge from '@/components/common/RoleBadge.vue';

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const ui = useUIStore();

const menuItems = computed(() => {
  if (auth.role === 'admin') {
    return [
      { key: '/admin/dashboard', label: '总览', icon: '📊' },
      { key: '/admin/projects', label: '全量项目', icon: '📋' },
      { key: 'sep', label: '— 浏览员工视图 —', disabled: true },
      { key: '/employee/dashboard', label: '员工工作台', icon: '👤' },
    ];
  }
  return [
    { key: '/employee/dashboard', label: '我的项目', icon: '📋' },
    { key: '/employee/projects/new', label: '+ 新建报门', icon: '✨' },
  ];
});

const selectedKeys = computed(() => [route.path]);

function onMenuClick({ key }: { key: string }) {
  if (key !== 'sep') router.push(key);
}

function logout() {
  auth.logout();
  router.push('/login');
}
</script>

<template>
  <a-layout style="min-height:100vh">
    <a-layout-sider :collapsed="ui.sidebarCollapsed" collapsible
                    @update:collapsed="ui.toggleSidebar()" theme="light">
      <div style="padding:16px;text-align:center;border-bottom:1px solid #eee">
        <strong>PatentlyPatent</strong>
      </div>
      <a-menu :selected-keys="selectedKeys" mode="inline" @click="onMenuClick">
        <template v-for="item in menuItems" :key="item.key">
          <a-menu-item v-if="!item.disabled" :key="item.key">
            <span>{{ item.icon }} {{ item.label }}</span>
          </a-menu-item>
          <a-menu-divider v-else />
        </template>
      </a-menu>
    </a-layout-sider>
    <a-layout>
      <a-layout-header style="background:#fff;padding:0 24px;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center">
        <span>{{ route.meta.title || '' }}</span>
        <span>
          {{ auth.user?.name }}
          <RoleBadge :role="auth.role" />
          <a-button type="link" size="small" @click="logout">退出</a-button>
        </span>
      </a-layout-header>
      <a-layout-content style="margin:24px;background:#fff;padding:24px;border-radius:6px">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>
```

- [ ] **Step 10.5: 跑 dev 验证布局编译过（暂时空白页可见）**

```bash
cd frontend
pnpm dev
```
Open `http://127.0.0.1:5173/patent/login`，应进入 Empty 兜底页（Task 11 写真 Login.vue 时替换）。控制台无错。

- [ ] **Step 10.6: 跑测试 + ts 检查**

```bash
pnpm test
pnpm exec vue-tsc -b --noEmit
```
Expected: 测试全绿；无 ts 错误。

- [ ] **Step 10.7: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/layouts/ frontend/src/components/common/RoleBadge.vue frontend/src/components/common/ReadonlyBanner.vue
git commit -m "feat(frontend): layouts (Default/Blank) + common badge/banner

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11：登录页 + 员工 Dashboard + ProjectNew

**Files:**
- Create: `frontend/src/views/login/Login.vue`
- Create: `frontend/src/views/employee/Dashboard.vue`
- Create: `frontend/src/views/employee/ProjectNew.vue`

- [ ] **Step 11.1: 写 views/login/Login.vue**

```vue
<script setup lang="ts">
import { useRouter } from 'vue-router';
import { authApi } from '@/api/auth';
import { useAuthStore } from '@/stores/auth';
import { message } from 'ant-design-vue';
import type { Role } from '@/types';

const router = useRouter();
const auth = useAuthStore();

async function loginAs(role: Role) {
  try {
    const user = await authApi.loginAs(role);
    auth.login(user);
    message.success(`已登录为 ${user.name}`);
    router.push(role === 'admin' ? '/admin/dashboard' : '/employee/dashboard');
  } catch (e) {
    message.error('登录失败：' + (e as Error).message);
  }
}
</script>

<template>
  <div style="display:flex;justify-content:center;align-items:center;min-height:100vh">
    <a-card title="PatentlyPatent · 原型演示" style="width:480px">
      <p style="color:#888;margin-bottom:24px">选择角色一键登录，无需密码（演示用）。</p>
      <div style="display:flex;gap:12px;flex-direction:column">
        <a-button type="primary" size="large" block @click="loginAs('employee')">
          👤 我是员工 — 报门 / 挖掘 / 起草交底书
        </a-button>
        <a-button size="large" block @click="loginAs('admin')">
          📊 我是管理员 — 看全量分布与项目
        </a-button>
      </div>
      <p style="color:#aaa;margin-top:32px;font-size:12px">
        本站 mock 数据驻留浏览器；刷新可重置。<br />
        部署：blind.pub/patent · 仓库：github.com/ChuangLee/PatentlyPatent
      </p>
    </a-card>
  </div>
</template>
```

- [ ] **Step 11.2: 写 views/employee/Dashboard.vue**

```vue
<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { useAuthStore } from '@/stores/auth';
import type { Project, ProjectStatus } from '@/types';

const router = useRouter();
const auth = useAuthStore();
const projects = ref<Project[]>([]);
const loading = ref(true);

onMounted(async () => {
  loading.value = true;
  projects.value = await projectsApi.list({ ownerId: auth.user!.id });
  loading.value = false;
});

const STATUS_LABEL: Record<ProjectStatus, { text: string; color: string }> = {
  drafting:    { text: '草稿', color: 'default' },
  researching: { text: '挖掘中', color: 'processing' },
  reporting:   { text: '检索完成', color: 'cyan' },
  submitted:   { text: '已提交存档', color: 'success' },
};

function go(p: Project) {
  if (p.status === 'drafting') router.push(`/employee/projects/${p.id}/mining`);
  else if (p.status === 'researching') router.push(`/employee/projects/${p.id}/mining`);
  else if (p.status === 'reporting') router.push(`/employee/projects/${p.id}/search`);
  else router.push(`/employee/projects/${p.id}/disclosure`);
}
</script>

<template>
  <a-page-header title="我的创新项目" sub-title="把工作中发现的创新点报上来，AI 帮你拆解并起草交底书" />

  <a-button type="primary" size="large" style="margin-bottom:24px"
            @click="router.push('/employee/projects/new')">
    ✨ 新建报门
  </a-button>

  <a-spin :spinning="loading">
    <a-empty v-if="!loading && projects.length === 0" description="还没有创新项目，点击上方'新建报门'开始"/>
    <a-row :gutter="[16, 16]" v-else>
      <a-col v-for="p in projects" :key="p.id" :xs="24" :md="12" :lg="8">
        <a-card hoverable :title="p.title" @click="go(p)">
          <template #extra>
            <a-tag :color="STATUS_LABEL[p.status].color">{{ STATUS_LABEL[p.status].text }}</a-tag>
          </template>
          <p style="color:#888;height:60px;overflow:hidden;text-overflow:ellipsis">{{ p.description }}</p>
          <p style="color:#aaa;font-size:12px;margin-top:12px">
            {{ p.domain }} · 更新 {{ new Date(p.updatedAt).toLocaleDateString() }}
          </p>
        </a-card>
      </a-col>
    </a-row>
  </a-spin>
</template>
```

- [ ] **Step 11.3: 写 views/employee/ProjectNew.vue**

```vue
<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { useAuthStore } from '@/stores/auth';
import { message } from 'ant-design-vue';
import type { Domain } from '@/types';

const router = useRouter();
const auth = useAuthStore();
const submitting = ref(false);

const form = reactive({
  title: '',
  description: '',
  domain: 'other' as Domain,
});

const DOMAINS: { value: Domain; label: string }[] = [
  { value: 'cryptography', label: '密码学' },
  { value: 'infosec', label: '信息安全' },
  { value: 'ai', label: '人工智能' },
  { value: 'other', label: '其他' },
];

async function submit() {
  if (!form.title.trim() || form.description.length < 30) {
    message.warning('标题不能为空，描述至少 30 字');
    return;
  }
  submitting.value = true;
  try {
    const p = await projectsApi.create({
      title: form.title,
      description: form.description,
      domain: form.domain,
      ownerId: auth.user!.id,
    });
    message.success('已创建，进入 AI 引导对话');
    router.push(`/employee/projects/${p.id}/mining`);
  } catch (e) {
    message.error('创建失败：' + (e as Error).message);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <a-page-header title="新建创新报门" @back="router.back()" />

  <a-form layout="vertical" style="max-width:720px">
    <a-form-item label="项目标题（10–50 字）" required>
      <a-input v-model:value="form.title" placeholder="例：基于 SIMD 的 Kyber-512 NTT 优化" :max-length="50" show-count />
    </a-form-item>

    <a-form-item label="技术领域" required>
      <a-select v-model:value="form.domain">
        <a-select-option v-for="d in DOMAINS" :key="d.value" :value="d.value">
          {{ d.label }}
        </a-select-option>
      </a-select>
    </a-form-item>

    <a-form-item label="一句话或几段描述（≥30 字，越详细 AI 引导越准）" required>
      <a-textarea v-model:value="form.description" :rows="6"
                  placeholder="例：我们在 ARM Cortex-M4 上对 Kyber-512 NTT 做了 SIMD 两路并行，密钥封装相对 PQClean 标量参考快了 38%，代码体积增加 1.8KB..." />
    </a-form-item>

    <a-form-item>
      <a-button type="primary" :loading="submitting" @click="submit">提交并进入 AI 引导 →</a-button>
    </a-form-item>
  </a-form>
</template>
```

- [ ] **Step 11.4: dev 测试登录跳转**

```bash
cd frontend
pnpm dev
```
打开 `http://127.0.0.1:5173/patent/login`，点 "我是员工" → 自动跳 `/employee/dashboard` → 看到 3 个 demo 项目卡片。点 "+ 新建报门" → 看到表单。

- [ ] **Step 11.5: 跑测试 + tsc**

```bash
pnpm test
pnpm exec vue-tsc -b --noEmit
```
Expected: 全绿。

- [ ] **Step 11.6: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/views/login/ frontend/src/views/employee/Dashboard.vue frontend/src/views/employee/ProjectNew.vue
git commit -m "feat(frontend): login + employee dashboard + project-new pages

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12：AgentChatStream + MiningSummaryPanel + ProjectMining 页

**Files:**
- Create: `frontend/src/components/chat/AgentChatStream.vue`
- Create: `frontend/src/components/chat/MiningSummaryPanel.vue`
- Create: `frontend/src/views/employee/ProjectMining.vue`

- [ ] **Step 12.1: 写 components/chat/AgentChatStream.vue（流式消息列表 + 输入框）**

```vue
<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { useChatStore } from '@/stores/chat';
import { chatApi } from '@/api/chat';
import { Button, Input } from 'ant-design-vue';

const props = defineProps<{ projectId: string; round: number }>();
const emit = defineEmits<{ (e: 'roundComplete', captured: string[]): void }>();

const chat = useChatStore();
const input = ref('');
const containerRef = ref<HTMLElement | null>(null);

watch(() => chat.messages.length, () => {
  nextTick(() => {
    if (containerRef.value) containerRef.value.scrollTop = containerRef.value.scrollHeight;
  });
}, { flush: 'post' });

async function send() {
  const text = input.value.trim();
  if (!text || chat.streaming) return;
  chat.appendUser(text);
  input.value = '';
  chat.startAgent();

  await chatApi.stream(props.projectId, props.round, text, e => {
    if (e.type === 'delta') chat.appendDelta(e.chunk);
    else if (e.type === 'fields') {
      chat.applyFields(e.captured);
      emit('roundComplete', e.captured);
    } else if (e.type === 'done') {
      chat.endAgent();
    }
  });
}
</script>

<template>
  <div style="display:flex;flex-direction:column;height:100%">
    <div ref="containerRef" style="flex:1;overflow-y:auto;padding:16px;background:#fafafa">
      <div v-if="chat.messages.length === 0" style="color:#aaa;text-align:center;padding-top:80px">
        尚未开始对话——发送第一条消息让 AI 开始引导。
      </div>
      <div v-for="m in chat.messages" :key="m.id"
           :style="{
             marginBottom: '16px',
             display:'flex',
             justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
           }">
        <div :style="{
          maxWidth: '70%',
          background: m.role === 'user' ? '#1677ff' : '#fff',
          color: m.role === 'user' ? '#fff' : '#1f2937',
          padding: '10px 14px', borderRadius: '12px',
          whiteSpace: 'pre-wrap', boxShadow: '0 1px 2px rgba(0,0,0,.06)',
        }">
          <span>{{ m.content }}</span>
          <span v-if="m.role === 'agent' && chat.streaming
                      && m.id === chat.messages[chat.messages.length-1].id"
                style="opacity:.4">|</span>
        </div>
      </div>
    </div>

    <div style="padding:12px;border-top:1px solid #eee;background:#fff">
      <div style="display:flex;gap:8px">
        <Input v-model:value="input" placeholder="描述你的发明，或回答 AI 的问题..."
               :disabled="chat.streaming" @press-enter="send" />
        <Button type="primary" :loading="chat.streaming" @click="send">发送</Button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 12.2: 写 components/chat/MiningSummaryPanel.vue**

```vue
<script setup lang="ts">
import { computed } from 'vue';
import { useChatStore } from '@/stores/chat';

const chat = useChatStore();

const groups = computed(() => {
  const g: Record<string, string[]> = { 领域: [], 问题: [], 手段: [], 效果: [], 区别: [] };
  for (const f of chat.capturedFields) {
    const [k, ...rest] = f.split(':');
    const v = rest.join(':');
    if (k in g) g[k].push(v);
  }
  return g;
});
</script>

<template>
  <div style="padding:16px">
    <h3 style="margin:0 0 16px 0">📌 已捕获要素</h3>
    <a-card v-for="(items, key) in groups" :key="key" size="small" style="margin-bottom:12px">
      <template #title>
        <span>{{ key }}</span>
        <a-badge :status="items.length ? 'success' : 'default'" style="margin-left:8px" />
      </template>
      <p v-if="items.length === 0" style="color:#aaa;margin:0">未捕获</p>
      <a-tag v-for="(item, i) in items" :key="i" color="blue" style="margin-bottom:4px">
        {{ item }}
      </a-tag>
    </a-card>
  </div>
</template>
```

- [ ] **Step 12.3: 写 views/employee/ProjectMining.vue**

```vue
<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { useChatStore } from '@/stores/chat';
import { useAuthStore } from '@/stores/auth';
import AgentChatStream from '@/components/chat/AgentChatStream.vue';
import MiningSummaryPanel from '@/components/chat/MiningSummaryPanel.vue';
import ReadonlyBanner from '@/components/common/ReadonlyBanner.vue';
import type { Project } from '@/types';
import { message } from 'ant-design-vue';

const route = useRoute();
const router = useRouter();
const chat = useChatStore();
const auth = useAuthStore();

const project = ref<Project | null>(null);
const round = ref(1);

const isReadonly = computed(() => auth.role === 'admin');

onMounted(async () => {
  chat.reset();
  project.value = await projectsApi.get(route.params.id as string);

  // demo case 已有 conversation，直接预填
  if (project.value?.miningSummary?.conversation.length) {
    for (const m of project.value.miningSummary.conversation) {
      if (m.role === 'user') chat.appendUser(m.content);
      else {
        chat.startAgent();
        chat.appendDelta(m.content);
        chat.endAgent();
      }
    }
    chat.applyFields(
      [...project.value.miningSummary.field.map(x => `领域:${x}`),
       ...project.value.miningSummary.problem.map(x => `问题:${x}`),
       ...project.value.miningSummary.means.map(x => `手段:${x}`),
       ...project.value.miningSummary.effect.map(x => `效果:${x}`),
       ...project.value.miningSummary.differentiator.map(x => `区别:${x}`)],
    );
    round.value = project.value.miningSummary.conversation.filter(m => m.role === 'agent').length + 1;
  }
});

function onRoundComplete() {
  round.value += 1;
}

function done() {
  message.success('要素已捕获完整，进入检索阶段');
  router.push(`/employee/projects/${route.params.id}/search`);
}
</script>

<template>
  <ReadonlyBanner :show="isReadonly" />
  <a-page-header :title="project?.title ?? '加载中...'"
                 sub-title="AI 引导对话 · 把模糊的发现拆成结构化创新点" />

  <div style="display:flex;height:calc(100vh - 240px);gap:16px">
    <div style="flex:1.5;border:1px solid #eee;border-radius:8px;display:flex;flex-direction:column">
      <AgentChatStream v-if="project" :project-id="project.id" :round="round"
                       @round-complete="onRoundComplete" />
    </div>

    <div style="flex:1;border:1px solid #eee;border-radius:8px;background:#fff;overflow-y:auto">
      <MiningSummaryPanel />
      <div style="padding:0 16px 16px">
        <a-button v-if="!isReadonly" type="primary" block size="large" @click="done">
          差不多了 →
        </a-button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 12.4: dev 端到端验证流式**

```bash
cd frontend
pnpm dev
```
1. 登录员工 → 工作台 → 点密码学卡片
2. 看到对话已预填 5 轮 + 右侧"已捕获要素"显示完整
3. 点击"差不多了" → 跳到 search 页（暂兜底空白）

- [ ] **Step 12.5: 跑测试 + tsc**

```bash
pnpm test
pnpm exec vue-tsc -b --noEmit
```
Expected: 测试全绿。

- [ ] **Step 12.6: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/components/chat/ frontend/src/views/employee/ProjectMining.vue
git commit -m "feat(frontend): agent chat stream + mining summary panel + ProjectMining view

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 13：PatentabilityCards + HitsTable + ProjectSearch 页

**Files:**
- Create: `frontend/src/components/search/PatentabilityCards.vue`
- Create: `frontend/src/components/search/HitsTable.vue`
- Create: `frontend/src/views/employee/ProjectSearch.vue`

- [ ] **Step 13.1: 写 components/search/PatentabilityCards.vue**

```vue
<script setup lang="ts">
import type { Patentability } from '@/types';

const props = defineProps<{ value: Patentability; rationale: string }>();

const META: Record<Patentability, { label: string; color: string; icon: string }> = {
  strong:           { label: '很可能新颖',     color: '#16a34a', icon: '🟢' },
  moderate:         { label: '边缘',           color: '#d97706', icon: '🟡' },
  weak:             { label: '创造性存疑',     color: '#ea580c', icon: '🟠' },
  not_recommended:  { label: '建议不申请',     color: '#dc2626', icon: '🔴' },
};
</script>

<template>
  <a-row :gutter="16" style="margin-bottom:16px">
    <a-col v-for="(meta, key) in META" :key="key" :span="6">
      <a-card :body-style="{
        textAlign:'center', borderTop: `4px solid ${meta.color}`,
        opacity: key === value ? 1 : 0.4,
        boxShadow: key === value ? '0 4px 12px rgba(0,0,0,0.08)' : 'none',
      }">
        <div style="font-size:32px">{{ meta.icon }}</div>
        <div style="font-weight:bold;margin-top:8px">{{ meta.label }}</div>
        <div v-if="key === value" style="color:#666;font-size:12px;margin-top:8px">当前结论</div>
      </a-card>
    </a-col>
  </a-row>

  <a-alert :message="rationale" type="info" show-icon style="margin-bottom:24px">
    <template #description>
      <a-collapse ghost>
        <a-collapse-panel key="pro" header="👨‍💼 专业版（A22.3 三步法说理）">
          <p style="color:#666;font-size:13px;line-height:1.7">
            按《专利审查指南》2023 三步法：① 确定最接近现有技术；② 确定区别特征与本申请实际解决的技术问题；
            ③ 判断是否显而易见。本结论基于对 8 篇命中文献的整体评估，建议代理师人工复核 D1 选择。
          </p>
        </a-collapse-panel>
      </a-collapse>
    </template>
  </a-alert>
</template>
```

- [ ] **Step 13.2: 写 components/search/HitsTable.vue**

```vue
<script setup lang="ts">
import type { PriorArtHit } from '@/types';
import { ref } from 'vue';

defineProps<{ hits: PriorArtHit[] }>();

const expanded = ref<string[]>([]);
const drawerHit = ref<PriorArtHit | null>(null);

const XYN_META = {
  X: { color: 'red', label: 'X · 破新颖' },
  Y: { color: 'orange', label: 'Y · 创造性结合' },
  N: { color: 'default', label: 'N · 不相关' },
} as const;

const columns = [
  { title: '公开号', dataIndex: 'id', width: 160 },
  { title: '标题', dataIndex: 'title', ellipsis: true },
  { title: '申请人', dataIndex: 'applicant', width: 140 },
  { title: '公布日', dataIndex: 'pubDate', width: 110 },
  { title: 'X/Y/N', dataIndex: 'xyn', width: 130, key: 'xyn' },
  { title: '操作', key: 'op', width: 120 },
];
</script>

<template>
  <a-table :data-source="hits" :columns="columns" :pagination="false" row-key="id"
           :expandable="{ expandedRowKeys: expanded, onExpandedRowsChange: (k) => expanded = k as string[] }">
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'xyn'">
        <a-tag :color="XYN_META[record.xyn].color">{{ XYN_META[record.xyn].label }}</a-tag>
      </template>
      <template v-else-if="column.key === 'op'">
        <a-button type="link" size="small" @click="drawerHit = record">详情 →</a-button>
      </template>
    </template>
    <template #expandedRowRender="{ record }">
      <a-row :gutter="16">
        <a-col :span="8">
          <strong>📌 问题对比</strong>
          <p>{{ record.comparison.problem }}</p>
        </a-col>
        <a-col :span="8">
          <strong>🔧 手段对比</strong>
          <p>{{ record.comparison.means }}</p>
        </a-col>
        <a-col :span="8">
          <strong>🎯 效果对比</strong>
          <p>{{ record.comparison.effect }}</p>
        </a-col>
      </a-row>
    </template>
  </a-table>

  <a-drawer :open="!!drawerHit" :title="drawerHit?.title" width="640" @close="drawerHit = null">
    <p><strong>公开号：</strong>{{ drawerHit?.id }}</p>
    <p><strong>申请人：</strong>{{ drawerHit?.applicant }}</p>
    <p><strong>公布日：</strong>{{ drawerHit?.pubDate }}</p>
    <p><strong>IPC：</strong>{{ drawerHit?.ipc.join(', ') }}</p>
    <a-divider />
    <p><strong>摘要：</strong></p>
    <p style="color:#555;line-height:1.7;white-space:pre-wrap">{{ drawerHit?.abstract }}</p>
  </a-drawer>
</template>
```

- [ ] **Step 13.3: 写 views/employee/ProjectSearch.vue**

```vue
<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { searchApi } from '@/api/search';
import { useAuthStore } from '@/stores/auth';
import PatentabilityCards from '@/components/search/PatentabilityCards.vue';
import HitsTable from '@/components/search/HitsTable.vue';
import ReadonlyBanner from '@/components/common/ReadonlyBanner.vue';
import type { Project, SearchReport } from '@/types';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const project = ref<Project | null>(null);
const report = ref<SearchReport | null>(null);
const loading = ref(true);

const isReadonly = computed(() => auth.role === 'admin');

onMounted(async () => {
  const id = route.params.id as string;
  project.value = await projectsApi.get(id);
  report.value = project.value?.searchReport
    ?? await searchApi.run(id);
  loading.value = false;
});

function next() {
  router.push(`/employee/projects/${route.params.id}/disclosure`);
}
</script>

<template>
  <ReadonlyBanner :show="isReadonly" />
  <a-page-header :title="project?.title ?? ''" sub-title="检索报告 · 4 档专利性结论 + 命中文献" />

  <a-spin :spinning="loading">
    <template v-if="report">
      <PatentabilityCards :value="report.patentability" :rationale="report.rationale" />
      <HitsTable :hits="report.hits" />
      <div style="margin-top:32px;text-align:center">
        <a-button v-if="!isReadonly" type="primary" size="large" @click="next">
          下一步：起草交底书 →
        </a-button>
      </div>
    </template>
  </a-spin>
</template>
```

- [ ] **Step 13.4: dev 测试**

```bash
pnpm dev
```
登录员工 → 密码学卡片 → mining 跳到 search → 看到 4 档卡片 + 8 条文献表格 + 行展开对照表 + 详情抽屉。

- [ ] **Step 13.5: 跑测试 + tsc**

```bash
pnpm test
pnpm exec vue-tsc -b --noEmit
```
Expected: 全绿。

- [ ] **Step 13.6: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/components/search/ frontend/src/views/employee/ProjectSearch.vue
git commit -m "feat(frontend): patentability cards + hits table + ProjectSearch view

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 14：ClaimTierSelector + TiptapEditor + ProjectDisclosure 页

**Files:**
- Create: `frontend/src/components/disclosure/ClaimTierSelector.vue`
- Create: `frontend/src/components/disclosure/TiptapEditor.vue`
- Create: `frontend/src/views/employee/ProjectDisclosure.vue`

- [ ] **Step 14.1: 写 components/disclosure/ClaimTierSelector.vue**

```vue
<script setup lang="ts">
import type { ClaimTier, Disclosure } from '@/types';

const props = defineProps<{
  claims: Disclosure['claims'];
  modelValue: ClaimTier;
}>();
const emit = defineEmits<{ (e: 'update:modelValue', t: ClaimTier): void }>();

const TIER_META: Record<ClaimTier, { label: string; size: string }> = {
  broad:  { label: '强档（特征 7±2）', size: '5±1' },
  medium: { label: '中档（特征 9±2）', size: '7±2' },
  narrow: { label: '弱档（特征 11±2）', size: '9±2' },
};
</script>

<template>
  <a-card title="独权概括度" size="small">
    <a-radio-group :value="modelValue" @update:value="(v: ClaimTier) => emit('update:modelValue', v)" button-style="solid">
      <a-radio-button v-for="t in (['broad','medium','narrow'] as ClaimTier[])" :key="t" :value="t">
        {{ TIER_META[t].label }}
      </a-radio-button>
    </a-radio-group>
    <a-alert v-if="claims.find(c => c.tier === modelValue)?.risk" type="warning" show-icon
             :message="claims.find(c => c.tier === modelValue)?.risk" style="margin-top:12px" />
  </a-card>
</template>
```

- [ ] **Step 14.2: 写 components/disclosure/TiptapEditor.vue**

```vue
<script setup lang="ts">
import { useEditor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import { watch } from 'vue';

const props = defineProps<{ modelValue: string; readonly?: boolean }>();
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>();

const editor = useEditor({
  content: props.modelValue,
  extensions: [StarterKit],
  editable: !props.readonly,
  onUpdate({ editor }) {
    emit('update:modelValue', editor.getHTML());
  },
});

watch(() => props.modelValue, (v) => {
  if (editor.value && v !== editor.value.getHTML()) editor.value.commands.setContent(v);
});

watch(() => props.readonly, (r) => {
  editor.value?.setEditable(!r);
});
</script>

<template>
  <div style="border:1px solid #d9d9d9;border-radius:6px;padding:12px;min-height:300px">
    <editor-content :editor="editor" />
  </div>
</template>

<style>
.ProseMirror { outline: none; min-height: 280px; line-height: 1.7; }
.ProseMirror h1, .ProseMirror h2, .ProseMirror h3 { margin: 16px 0 8px; }
.ProseMirror p { margin: 0 0 8px; }
</style>
```

- [ ] **Step 14.3: 写 views/employee/ProjectDisclosure.vue**

```vue
<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { disclosureApi } from '@/api/disclosure';
import { useAuthStore } from '@/stores/auth';
import ClaimTierSelector from '@/components/disclosure/ClaimTierSelector.vue';
import TiptapEditor from '@/components/disclosure/TiptapEditor.vue';
import ReadonlyBanner from '@/components/common/ReadonlyBanner.vue';
import { message, Modal } from 'ant-design-vue';
import type { Project, ClaimTier } from '@/types';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const project = ref<Project | null>(null);
const tier = ref<ClaimTier>('medium');
const body = ref<string>('');
const submitting = ref(false);

const isReadonly = computed(() => auth.role === 'admin');
const isSubmitted = computed(() => project.value?.status === 'submitted');

onMounted(async () => {
  const id = route.params.id as string;
  project.value = await projectsApi.get(id);
  if (project.value?.disclosure) {
    body.value = renderHtml(project.value.disclosure);
    const broad = project.value.disclosure.claims.find(c => c.tier === 'broad');
    if (broad) tier.value = 'medium'; // 默认中档
  }
});

function renderHtml(d: { technicalField: string; background: string; summary: string; embodiments: string }): string {
  return `<h2>技术领域</h2><p>${d.technicalField}</p>
          <h2>背景技术</h2><p>${d.background}</p>
          <h2>发明内容</h2><p>${d.summary}</p>
          <h2>具体实施方式</h2><p>${d.embodiments}</p>`;
}

async function changeTier(t: ClaimTier) {
  tier.value = t;
  if (!project.value) return;
  const d = await disclosureApi.selectClaimTier(project.value.id, t);
  body.value = renderHtml({
    technicalField: d.technicalField,
    background: d.background,
    summary: d.summary,
    embodiments: d.embodiments,
  });
  message.info(`已切换到 ${t} 档独权`);
}

function copyMarkdown() {
  const md = body.value
    .replace(/<h2>/g, '\n## ').replace(/<\/h2>/g, '\n')
    .replace(/<p>/g, '').replace(/<\/p>/g, '\n')
    .replace(/<[^>]+>/g, '');
  navigator.clipboard.writeText(md);
  message.success('Markdown 已复制到剪贴板');
}

function exportDocx() {
  message.info('v0.2 支持真实 docx 导出，目前已下载占位 .docx 文件（演示）');
}

async function submit() {
  if (!project.value) return;
  Modal.confirm({
    title: '确认提交存档？',
    content: '提交后将由 IP 部门线下处理；可以"取消提交"回退编辑。',
    async onOk() {
      submitting.value = true;
      try {
        await projectsApi.submit(project.value!.id);
        project.value!.status = 'submitted';
        message.success('已提交至 IP 部门，将由专员线下处理');
      } finally { submitting.value = false; }
    },
  });
}

async function unsubmit() {
  if (!project.value) return;
  await projectsApi.unsubmit(project.value.id);
  project.value.status = 'reporting';
  message.info('已取消提交，可继续编辑');
}
</script>

<template>
  <ReadonlyBanner :show="isReadonly" />
  <a-page-header :title="project?.title ?? ''" sub-title="交底书编辑 · 三档独权切换" />

  <ClaimTierSelector v-if="project?.disclosure"
                     :claims="project.disclosure.claims"
                     :model-value="tier"
                     :readonly="isReadonly || isSubmitted"
                     @update:model-value="changeTier" />

  <a-divider />

  <TiptapEditor v-model="body" :readonly="isReadonly || isSubmitted" />

  <div style="margin-top:24px;display:flex;gap:12px;justify-content:space-between">
    <a-space>
      <a-button @click="copyMarkdown">复制 Markdown</a-button>
      <a-button @click="exportDocx">导出 docx</a-button>
    </a-space>
    <a-space v-if="!isReadonly">
      <a-button v-if="isSubmitted" danger @click="unsubmit">取消提交，回退编辑</a-button>
      <a-button v-else type="primary" :loading="submitting" @click="submit">提交存档 →</a-button>
    </a-space>
  </div>
</template>
```

- [ ] **Step 14.4: dev 端到端验证**

```bash
pnpm dev
```
1. 员工 → 信息安全 case → 走到 disclosure（已 submitted）
2. 看到三档切换、Tiptap 编辑器、"取消提交，回退编辑"按钮
3. 切换到 AI case（drafting）→ 看到 "提交存档" 按钮，点击确认 → 状态变 submitted

- [ ] **Step 14.5: 跑测试 + tsc**

```bash
pnpm test
pnpm exec vue-tsc -b --noEmit
```
Expected: 全绿。

- [ ] **Step 14.6: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/components/disclosure/ frontend/src/views/employee/ProjectDisclosure.vue
git commit -m "feat(frontend): claim tier selector + Tiptap editor + ProjectDisclosure view

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 15：管理员 Dashboard + Projects 页（含 ECharts）

**Files:**
- Create: `frontend/src/views/admin/Dashboard.vue`
- Create: `frontend/src/views/admin/Projects.vue`

- [ ] **Step 15.1: 写 views/admin/Dashboard.vue**

```vue
<script setup lang="ts">
import { onMounted, ref, computed, watch, nextTick } from 'vue';
import { projectsApi } from '@/api/projects';
import * as echarts from 'echarts';
import type { Project, ProjectStatus, Patentability } from '@/types';

const projects = ref<Project[]>([]);
const statusChartRef = ref<HTMLDivElement | null>(null);
const patChartRef = ref<HTMLDivElement | null>(null);

const STATUS_LABEL: Record<ProjectStatus, string> = {
  drafting: '草稿', researching: '挖掘中', reporting: '检索完成', submitted: '已提交',
};
const PAT_LABEL: Record<Patentability, string> = {
  strong: '很可能新颖', moderate: '边缘', weak: '存疑', not_recommended: '不建议',
};

const stats = computed(() => {
  const byStatus: Record<string, number> = {};
  const byPat: Record<string, number> = {};
  for (const p of projects.value) {
    byStatus[STATUS_LABEL[p.status]] = (byStatus[STATUS_LABEL[p.status]] ?? 0) + 1;
    const pat = p.searchReport?.patentability;
    if (pat) byPat[PAT_LABEL[pat]] = (byPat[PAT_LABEL[pat]] ?? 0) + 1;
  }
  return { byStatus, byPat };
});

onMounted(async () => {
  projects.value = await projectsApi.list();
  await nextTick();
  drawCharts();
});

watch(stats, () => drawCharts(), { deep: true });

function drawCharts() {
  if (statusChartRef.value) {
    echarts.init(statusChartRef.value).setOption({
      title: { text: '项目状态分布', left: 'center' },
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type: 'pie', radius: '60%',
        data: Object.entries(stats.value.byStatus).map(([n, v]) => ({ name: n, value: v })),
      }],
    });
  }
  if (patChartRef.value) {
    echarts.init(patChartRef.value).setOption({
      title: { text: '专利性结论分布', left: 'center' },
      tooltip: {},
      xAxis: { type: 'category', data: Object.keys(stats.value.byPat) },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: Object.values(stats.value.byPat), itemStyle: { color: '#1677ff' } }],
    });
  }
}
</script>

<template>
  <a-page-header title="管理员总览" sub-title="全公司创新挖掘活动一览" />

  <a-row :gutter="16">
    <a-col :span="12">
      <a-card>
        <div ref="statusChartRef" style="height:300px"></div>
      </a-card>
    </a-col>
    <a-col :span="12">
      <a-card>
        <div ref="patChartRef" style="height:300px"></div>
      </a-card>
    </a-col>
  </a-row>

  <a-row :gutter="16" style="margin-top:16px">
    <a-col :span="6">
      <a-card><a-statistic title="项目总数" :value="projects.length" /></a-card>
    </a-col>
    <a-col :span="6">
      <a-card>
        <a-statistic title="智慧芽配额"
                     :value="42" suffix="/ 100" :value-style="{ color: '#16a34a' }" />
      </a-card>
    </a-col>
    <a-col :span="6">
      <a-card>
        <a-statistic title="LLM tokens (今日)"
                     :value="183_240" :value-style="{ color: '#1677ff' }" />
      </a-card>
    </a-col>
    <a-col :span="6">
      <a-card>
        <a-statistic title="已提交存档"
                     :value="(stats.byStatus['已提交'] ?? 0)"
                     :value-style="{ color: '#16a34a' }" />
      </a-card>
    </a-col>
  </a-row>
</template>
```

- [ ] **Step 15.2: 写 views/admin/Projects.vue**

```vue
<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { projectsApi } from '@/api/projects';
import type { Project, Domain, ProjectStatus } from '@/types';

const router = useRouter();
const projects = ref<Project[]>([]);
const filterDomain = ref<Domain | ''>('');
const filterStatus = ref<ProjectStatus | ''>('');

const STATUS_META: Record<ProjectStatus, string> = {
  drafting: '草稿', researching: '挖掘中', reporting: '检索完成', submitted: '已提交',
};
const DOMAIN_META: Record<Domain, string> = {
  cryptography: '密码学', infosec: '信息安全', ai: '人工智能', other: '其他',
};

const filtered = computed(() =>
  projects.value.filter(p =>
    (!filterDomain.value || p.domain === filterDomain.value) &&
    (!filterStatus.value || p.status === filterStatus.value),
  ),
);

const columns = [
  { title: '标题', dataIndex: 'title', ellipsis: true },
  { title: '员工', key: 'owner', width: 100 },
  { title: '领域', dataIndex: 'domain', width: 100, key: 'domain' },
  { title: '状态', dataIndex: 'status', width: 110, key: 'status' },
  { title: '专利性', key: 'pat', width: 110 },
  { title: '更新时间', dataIndex: 'updatedAt', width: 140, key: 'updatedAt' },
];

onMounted(async () => { projects.value = await projectsApi.list(); });

function viewProject(p: Project) {
  router.push(`/employee/projects/${p.id}/disclosure`);
}
</script>

<template>
  <a-page-header title="全量项目" sub-title="只读视角 · 用于走查与统计" />

  <a-space style="margin-bottom:16px">
    <a-select v-model:value="filterDomain" placeholder="按领域过滤" allow-clear style="width:160px">
      <a-select-option v-for="(label, key) in DOMAIN_META" :key="key" :value="key">{{ label }}</a-select-option>
    </a-select>
    <a-select v-model:value="filterStatus" placeholder="按状态过滤" allow-clear style="width:160px">
      <a-select-option v-for="(label, key) in STATUS_META" :key="key" :value="key">{{ label }}</a-select-option>
    </a-select>
  </a-space>

  <a-table :data-source="filtered" :columns="columns" row-key="id"
           :custom-row="(record) => ({ onClick: () => viewProject(record), style: { cursor: 'pointer' } })">
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'owner'">u1 张工程师</template>
      <template v-else-if="column.key === 'domain'">{{ DOMAIN_META[record.domain] }}</template>
      <template v-else-if="column.key === 'status'">
        <a-tag>{{ STATUS_META[record.status] }}</a-tag>
      </template>
      <template v-else-if="column.key === 'pat'">
        <a-tag v-if="record.searchReport"
               :color="record.searchReport.patentability === 'strong' ? 'green' :
                       record.searchReport.patentability === 'moderate' ? 'gold' :
                       record.searchReport.patentability === 'weak' ? 'orange' : 'red'">
          {{ record.searchReport.patentability }}
        </a-tag>
        <span v-else style="color:#aaa">-</span>
      </template>
      <template v-else-if="column.key === 'updatedAt'">
        {{ new Date(record.updatedAt).toLocaleString('zh-CN', { hour12: false }) }}
      </template>
    </template>
  </a-table>
</template>
```

- [ ] **Step 15.3: dev 验证 admin**

```bash
pnpm dev
```
1. 切到管理员 → 看到 dashboard 饼图 + 柱图 + 4 个 Statistic
2. 切到全量项目 → 表格 + 过滤；点行进员工 disclosure 页 → 看到顶部"只读 (admin 视角)"红条 + 编辑按钮隐藏

- [ ] **Step 15.4: 跑测试 + tsc**

```bash
pnpm test
pnpm exec vue-tsc -b --noEmit
```
Expected: 全绿。

- [ ] **Step 15.5: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/views/admin/
git commit -m "feat(frontend): admin dashboard (ECharts) + projects table

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 16：错误页 + 部署脚本 + nginx 片段 + 真实部署 + 自检

**Files:**
- Create: `frontend/src/views/error/Forbidden.vue` `frontend/src/views/error/NotFound.vue`
- Create: `frontend/scripts/deploy.sh`
- Create: `frontend/nginx/patent.conf.snippet`
- Create: `frontend/README.md`

- [ ] **Step 16.1: 写 views/error/Forbidden.vue**

```vue
<script setup lang="ts">
import { useRouter } from 'vue-router';
const router = useRouter();
</script>
<template>
  <a-result status="403" title="403" sub-title="你没有访问此页面的权限">
    <template #extra>
      <a-button type="primary" @click="router.push('/login')">回登录页</a-button>
    </template>
  </a-result>
</template>
```

- [ ] **Step 16.2: 写 views/error/NotFound.vue**

```vue
<script setup lang="ts">
import { useRouter } from 'vue-router';
const router = useRouter();
</script>
<template>
  <a-result status="404" title="404" sub-title="页面不存在">
    <template #extra>
      <a-button type="primary" @click="router.push('/')">回首页</a-button>
    </template>
  </a-result>
</template>
```

- [ ] **Step 16.3: 写 scripts/deploy.sh**

```bash
#!/usr/bin/env bash
# 部署 frontend dist 到 /var/www/patent；重载 nginx
set -euo pipefail

DIST="$(dirname "$0")/../dist"
TARGET=/var/www/patent

if [ ! -d "$DIST" ]; then
  echo "ERROR: $DIST 不存在，先 pnpm build"; exit 1
fi

sudo mkdir -p "$TARGET"
sudo rsync -av --delete "$DIST"/ "$TARGET"/
sudo nginx -t && sudo nginx -s reload
echo "✓ deployed to https://blind.pub/patent/"
```

- [ ] **Step 16.4: 写 nginx/patent.conf.snippet**

```nginx
# 把以下 location 块加到 /etc/nginx/conf.d/3xui.conf 的 server_name blind.pub 块内：

location = /patent {
    return 301 /patent/;
}

location /patent/ {
    alias /var/www/patent/;
    index index.html;
    try_files $uri $uri/ /patent/index.html;

    # MSW worker 必须有正确 MIME 与 Service-Worker-Allowed
    location ~ ^/patent/mockServiceWorker\.js$ {
        alias /var/www/patent/mockServiceWorker.js;
        types { } default_type application/javascript;
        add_header Service-Worker-Allowed "/patent/";
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # 静态资源长缓存
    location ~* /patent/assets/.*\.(js|css|png|jpg|svg|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # index.html 不缓存（保证发版即生效）
    add_header Cache-Control "no-cache, no-store, must-revalidate";

    # 防搜索引擎收录
    add_header X-Robots-Tag "noindex, nofollow";
}
```

- [ ] **Step 16.5: 写 frontend/README.md**

```markdown
# PatentlyPatent · Frontend Prototype

mid-fi 交互原型（MSW 全 mock 拦截 + 双角色完整闭环）。

## 开发

```bash
pnpm install
pnpm dev          # http://127.0.0.1:5173/patent/
pnpm test         # 单测
pnpm build        # 构建到 dist/
pnpm preview      # 预览构建产物
```

## 部署到 blind.pub/patent

1. 一次性把 `nginx/patent.conf.snippet` 的内容追加到 `/etc/nginx/conf.d/3xui.conf` 的 `server_name blind.pub` 块内（已有 acme/SSL 证书复用）
2. `sudo nginx -t && sudo nginx -s reload`
3. 后续每次 `pnpm deploy` 自动 build + rsync + reload

## 角色

- **员工**：登录后报门 → AI 引导对话 → 检索报告 → 起草交底书 → 提交存档
- **管理员**：登录后看分布饼图 + 全量项目表；点项目进员工页变只读模式

## Demo Data

3 个真实可读 case（密码学/信息安全/AI），刷新页面会重置（数据驻留浏览器内存与 sessionStorage）。

## 切真后端

把 `src/api/client.ts` 的 `baseURL` 改成真实后端地址，关掉 MSW（`main.ts` 的 `enableMocking()`），业务代码不动。
```

- [ ] **Step 16.6: 本地构建+预览验证**

```bash
cd frontend
pnpm build
pnpm preview
```
Expected: dist/ 生成；预览端口可访问 `/patent/`，全流程跑通。

- [ ] **Step 16.7: 加 nginx location 块（人工 sudo）**

```bash
# 备份现配
sudo cp /etc/nginx/conf.d/3xui.conf /etc/nginx/conf.d/3xui.conf.bak.$(date +%s)

# 把 frontend/nginx/patent.conf.snippet 内容粘到 server_name blind.pub 块内（编辑器或 sed）
sudo $EDITOR /etc/nginx/conf.d/3xui.conf

sudo nginx -t
# 通过后：
sudo nginx -s reload
```

- [ ] **Step 16.8: 部署**

```bash
cd frontend
chmod +x scripts/deploy.sh
pnpm deploy
```
Expected: rsync 成功；`✓ deployed` 输出。

- [ ] **Step 16.9: 自检**

```bash
curl -I https://blind.pub/patent/                              # 应 200
curl -I https://blind.pub/patent/mockServiceWorker.js          # 应 200，Content-Type: application/javascript
curl -sS https://blind.pub/patent/ | grep -c '<div id="app"'   # 应 ≥ 1
```

- [ ] **Step 16.10: 浏览器端到端走通**

打开 `https://blind.pub/patent/login`：
1. 点员工 → 看到 3 个 demo 项目
2. 点密码学卡片 → mining 页对话已预填，右侧要素全
3. "差不多了" → search → 看到 4 档 + 8 文献
4. "下一步" → disclosure → 三档切换 + Tiptap 编辑 + 已 submitted 状态
5. 退出 → 切管理员 → 看到 dashboard + 全量项目表
6. 表格点行 → 进 disclosure 红条只读 + 按钮隐藏
7. 越权测试：直接访问 `/patent/admin/dashboard` 时切到 employee → 跳 403

- [ ] **Step 16.11: Commit**

```bash
cd /root/ai-workspace/patent_king
git add frontend/src/views/error/ frontend/scripts/deploy.sh \
  frontend/nginx/patent.conf.snippet frontend/README.md
git commit -m "feat(frontend): error pages + deploy script + nginx snippet + README

Deployed to https://blind.pub/patent/

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

## 验收对照（来自 spec §9）

- [ ] 员工角色：3 个 demo case 全跑通（密码学 submitted、信息安全 submitted、AI drafting）
- [ ] 流式对话视感与真 LLM 流式无明显差异
- [ ] 管理员角色：dashboard 看到 3 个项目状态/结论分布；admin/projects 表格能筛能排
- [ ] 两种角色一键切换，受 RBAC 路由守卫保护，越权跳 403
- [ ] 部署 `https://blind.pub/patent/` 可访问，刷新不 404
- [ ] MSW worker 注册成功（DevTools Application / Service Workers 看见）
- [ ] 移动端简单适配（Soybean / Antd 默认）
