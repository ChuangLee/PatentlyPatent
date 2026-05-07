---
spec: PatentlyPatent v0 原型前端设计
version: 0.1
date: 2026-05-07
author: ChuangLee + Claude (brainstorming session)
status: draft, awaiting user review
parent: docs/requirements_v2.md
sub_project: D' (前端体验原型，v2 七子项目分解中的精简前置版)
---

# PatentlyPatent · v0 原型前端设计

## 项目位置

新建子目录 `frontend/`（与现有 `pk/` v1 包并列），所有代码独立，互不影响：

```
patent_king/                    # GitHub: ChuangLee/PatentlyPatent
├── pk/                         # v1 Python CLI（原样保留）
├── frontend/                   # ⭐ 本 spec 范围：v0 原型
│   ├── src/  public/  ...      # （详见架构总览）
│   ├── package.json
│   └── vite.config.ts
├── docs/superpowers/specs/<本文件>
└── ... （其它 v1 资产保留）
```

## 0. 目的与范围

目的：交付一个**纯前端 mid-fi 交互原型**，部署在 `https://blind.pub/patent/`，让员工/IP reviewer/admin 三种角色能完整走完"创新报门 → agent 引导 → 检索报告 → 交底书 → reviewer 审阅"的产品故事，作为对标方案给老板/客户/早期用户演示。

非目的（明确不做）：
- 不真起后端、不调真 LLM API、不接智慧芽真实数据
- 不做用户注册/真密码登录（演示用一键切角色按钮）
- 不做权限粒度精细化（前端 mock RBAC 即可）
- 不做附图生成、附件上传真存储
- 不做 docx 真导出（按钮只 toast）

成功标准：
- 任意访问者打开 `https://blind.pub/patent/login`，1 分钟内能体验完员工全流程；3 分钟内能从员工切到 reviewer 看到流转后审阅页面；admin 总览页 30 秒内能看到全量项目分布
- 流式对话视感与真 LLM 流式无异（按字符 chunk + 25-60ms 节奏）
- 无任何后端依赖，nginx 静态部署即可

## 1. 已敲定决策（来自 brainstorming）

| 维度 | 决策 |
|---|---|
| 保真度 | mid-fi 交互原型，Mock Service Worker 拦截 fetch |
| 故事 | 双角色完整闭环（员工 + IP reviewer + admin），约 10 页 |
| 起手模板 | Soybean Admin v1.x，AntD Vue 4.x 分支 |
| Demo 数据 | 3 个领域完整 case：密码学 / 信息安全 / AI |
| 流式 | 前端伪流式（MSW 返 SSE chunked，按 token 子串延迟释放） |
| 部署 | `https://blind.pub/patent/`，history 模式 + nginx fallback |
| 国际化 | v0.1 **硬编码中文字串**（不引入 vue-i18n），避免提前优化；v0.2 一次性接 vue-i18n |
| 视觉 | Soybean 默认主题（蓝色），暗色模式可切换；不做品牌定制 |

## 2. 架构总览

```
patently-prototype/                # 独立子目录，前端原型
├── src/
│   ├── views/                     # 10 个页面组件
│   ├── components/                # 共用组件
│   ├── stores/                    # Pinia
│   ├── router/                    # vue-router，base = '/patent/'
│   ├── mock/                      # MSW handlers + 3 个 demo case fixtures
│   │   ├── handlers/              # auth/projects/chat/search/disclosure
│   │   ├── fixtures/
│   │   │   ├── case_crypto.ts     # 密码学 case
│   │   │   ├── case_infosec.ts    # 信息安全 case
│   │   │   └── case_ai.ts         # AI case
│   │   └── browser.ts             # MSW worker 启动
│   ├── api/                       # axios + typed 请求函数
│   ├── types/                     # TS interfaces
│   └── App.vue / main.ts
├── public/
│   └── mockServiceWorker.js       # MSW 注册的 service worker
├── vite.config.ts                 # base: '/patent/'
├── package.json
└── README.md
```

**核心理念**：所有外部交互一律走 `src/api/*`（typed），MSW 在 service-worker 层透明拦截 → 未来切真后端**只改 axios baseURL**，业务代码不动。

### 备选与拒绝

| 备选 | 拒绝理由 |
|---|---|
| 把 mock 数据写死在 store/components 里 | 切真后端要全局改业务代码，违反"原型→生产"平滑过渡 |
| 用 json-server 起本地 mock 服务 | 多了一个进程，nginx 静态站不可达；MSW 跑在浏览器内最干净 |
| 不用模板从零起 | 浪费 2-3 天写 layout/侧栏/面包屑/主题；Soybean 已经包好 |

## 3. 路由清单（10 页）

base = `/patent/`

| # | 路径 | 页面名 | 谁能进 | 用途 |
|---|---|---|---|---|
| 1 | `/login` | 登录页 | 公开 | 一键切角色（员工/reviewer/admin） |
| 2 | `/employee/dashboard` | 员工工作台 | 员工 | 项目卡片墙 + "+新建报门" |
| 3 | `/employee/projects/new` | 创建报门 | 员工 | 标题+描述+领域 |
| 4 | `/employee/projects/:id/mining` | Agent 引导对话 | 员工 | 流式对话 + 实时要素面板 |
| 5 | `/employee/projects/:id/search` | 检索报告 | 员工 | 4 档结论 + 命中文献 |
| 6 | `/employee/projects/:id/disclosure` | 交底书编辑 | 员工 | Tiptap + 三档独权切换器 |
| 7 | `/reviewer/inbox` | reviewer 收件箱 | reviewer | 待审项目列表 |
| 8 | `/reviewer/projects/:id/review` | reviewer 审阅页 | reviewer | 交底书+批注侧栏+状态切换 |
| 9 | `/admin/dashboard` | admin 总览 | admin | 项目分布饼图 + 配额条 |
| 10 | `/admin/projects` | 全量项目 | admin | 全部项目表格+多维过滤 |
| - | `/403` `/404` | 兜底 | — | 越权/未找到 |

### 公共骨架
- Soybean Admin 默认壳（顶栏 logo + 用户菜单 + 角色徽章；侧栏按角色动态菜单；面包屑沿 router meta）
- 项目状态机（含转换条件）：

```
drafting ──[创建提交]──→ researching ──[mining 完成]──→ reporting
                                                            │
                       ┌──[reviewer 退回补充]──[员工提交]──┘
                       │                              │
                       ↓                              ↓
                  drafting ←──────────────────── submitted
                                                       │
                                                  [reviewer 看]
                                                       ↓
                                                  reviewing
                                            ┌──────────┼──────────┐
                                       [批准]      [退回补充]   [拒绝]
                                            ↓          ↓          ↓
                                       approved   drafting    rejected
```
对应路径 3→4→5→6→submit→7→8。"退回补充"使状态回到 `drafting`，员工可重启对话/检索/编辑。

### 角色权限（前端 mock RBAC）

```ts
// stores/auth.ts
type Role = 'employee' | 'reviewer' | 'admin';

const RBAC: Record<Role, RegExp[]> = {
  employee: [/^\/patent\/employee\//],
  reviewer: [
    /^\/patent\/reviewer\//,
    /^\/patent\/employee\/projects\/.*\/(disclosure|search)$/,  // 复用员工 readonly 视图
  ],
  admin: [/^\/patent\/admin\//, /^\/patent\/(employee|reviewer)\//],
};
```

登录页一键切角色（无密码、纯演示），切完 Pinia 持久化到 localStorage。

## 4. 数据模型

```ts
// types/index.ts
export type Role = 'employee' | 'reviewer' | 'admin';
export type ProjectStatus = 'drafting' | 'researching' | 'reporting'
                          | 'submitted' | 'reviewing' | 'approved' | 'rejected';
export type Domain = 'cryptography' | 'infosec' | 'ai' | 'other';
export type Patentability = 'strong' | 'moderate' | 'weak' | 'not_recommended';
export type ClaimTier = 'broad' | 'medium' | 'narrow';
export type XYNTag = 'X' | 'Y' | 'N';

export interface User {
  id: string; name: string; role: Role; department: string; avatar?: string;
}

export interface Project {
  id: string;
  title: string;
  domain: Domain;
  description: string;
  status: ProjectStatus;
  ownerId: string;
  reviewerId?: string;
  createdAt: string;
  updatedAt: string;
  miningSummary?: MiningSummary;
  searchReport?: SearchReport;
  disclosure?: Disclosure;
  reviewerNotes?: ReviewerNote[];
}

export interface MiningSummary {
  field: string[];
  problem: string[];
  means: string[];
  effect: string[];
  differentiator: string[];
  conversation: ChatMessage[];
}

export interface ChatMessage {
  id: string;
  role: 'agent' | 'user';
  content: string;
  ts: string;
  meta?: { stage?: '5why'|'whatif'|'generalize'|'effect'; capturedFields?: string[] };
}

export interface SearchReport {
  patentability: Patentability;
  rationale: string;
  hits: PriorArtHit[];
}

export interface PriorArtHit {
  id: string;
  title: string; abstract: string;
  applicant: string; pubDate: string;
  ipc: string[]; xyn: XYNTag;
  comparison: { problem: string; means: string; effect: string };
  url?: string;
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

export interface ReviewerNote {
  id: string; reviewerId: string; ts: string;
  anchor: { section: string; offset?: number };
  comment: string;
  type: 'suggest' | 'block' | 'praise';
}
```

## 5. 三个 Demo Case 内容

| Case | 标题 | 报门一句话 | 4 档结论 | reviewer 流转 |
|---|---|---|---|---|
| **🔐 密码学** | 一种基于 Kyber-512 NTT 并行优化的轻量级 PQC KEM 实现 | NIST 后量子标准 Kyber 的 NTT 子运算做了通道并行+向量化，嵌入式 ARM Cortex-M4 上密钥封装快了 38%。 | **moderate** | 待审 reviewing，2 条批注（D1 区别要写清；补 Falcon-512、Dilithium-2 同台 latency 对照） |
| **🛡️ 信息安全** | 一种基于多信号融合行为基线的 API 网关异常请求检测方法与系统 | 在企业 API 网关里把统计 z-score + 梯度提升 ML + 滑动窗口自适应阈值三路信号融合，做账号纬度异常调用检测，误报率低 40%。 | **strong** | 已通过 approved，1 条 reviewer 嘉奖批注（建议在权要 6 增加'用户可解释性'相关从权） |
| **🤖 AI** | 一种基于 KV-cache 分页与请求级动态调度的大模型推理批处理方法 | KV-cache 分页 + 优先级请求调度，单 GPU 提升大模型推理吞吐 2.3 倍。 | **weak** | 退回补充 rejected→drafting，2 条批注（vLLM PagedAttention SOSP'23 已公开作为独权将被 X 类破新颖；建议聚焦到非首推用户场景下的优先级调度） |

每个 case 预置完整数据：报门描述 + 5 轮对话 + 8 篇命中文献（公开号真实存在，摘要+对照表为编造，页面角标"演示数据"）+ 4 档结论 + 三档独权 + 完整说明书五段骨架 + reviewer 批注。

### Mock 文献库分布（共 24 条）

| Case | 8 条命中分布 | 关键 X/Y 文献举例 |
|---|---|---|
| 密码学 | 0 X / 3 Y / 5 N | Y: Kyber NTT 标量优化、CHES'24 Cortex-M Kyber 等 |
| 信息安全 | 0 X / 2 Y / 6 N | Y: z-score 单一信号检测、GBDT 用户行为分类 |
| AI | 2 X / 3 Y / 3 N | X: vLLM PagedAttention 论文、CN 同等申请；Y: continuous batching 早期方法 |

### Mock 用户

```ts
const DEMO_USERS = [
  { id: 'u1', name: '张工程师', role: 'employee', department: '研发-AI 平台部' },
  { id: 'u2', name: '李审阅师', role: 'reviewer', department: '研发-AI 平台部' },
  { id: 'u3', name: '王管理员', role: 'admin', department: 'IP 总部' },
];
```

## 6. 关键交互细节

### 6.1 Agent 引导对话 — 前端伪流式

MSW 拦截 `POST /api/projects/:id/chat`，返回 SSE 流：

```ts
// mock/handlers/chat.ts
http.post('/api/projects/:id/chat', async ({ params, request }) => {
  const { round, userMsg } = await request.json();
  const script = getCaseScript(params.id, round);
  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();
      controller.enqueue(encoder.encode(`event: thinking\ndata: {}\n\n`));
      await sleep(400);
      for (const chunk of splitByGrapheme(script.text, 3)) {
        controller.enqueue(encoder.encode(
          `event: delta\ndata: ${JSON.stringify({chunk})}\n\n`));
        await sleep(rand(25, 60));
      }
      controller.enqueue(encoder.encode(
        `event: fields\ndata: ${JSON.stringify({captured: script.capturedFields})}\n\n`));
      controller.enqueue(encoder.encode(`event: done\ndata: {}\n\n`));
      controller.close();
    }
  });
  return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream' } });
});
```

前端用 fetch + `body.getReader()` 消费：
- `delta` → 追加到当前 message.content
- `fields` → Pinia chatStore.applyFields()，右侧"已捕获要素"面板字段闪烁高亮 1.5s
- `done` → 解锁输入框

节奏：3 字符/chunk + 25-60ms 抖动 ≈ 60 字/秒。

### 6.2 实时结构化要素面板（Mining 页右侧）

5 类要素卡片：领域 / 问题 / 手段 / 效果 / 区别现有
- 卡片右上角小灯：未捕获(灰)/捕获中(蓝闪)/已确认(绿)
- 可手动编辑（点项弹小输入框）— 演示"agent 漏的人能补"

### 6.3 检索报告页

- 顶部 4 档专利性结论卡片（绿/黄/橙/红 配色），人话解释 + "专业版"展开 A22.3 三步法说理
- 命中文献表格（X 红 / Y 橙 / N 灰）
- 行内展开三栏对照（问题/手段/效果），点 [→] 抽屉看摘要

### 6.4 交底书编辑（Tiptap）

- 三档独权切换器（Radio.Group）：强(7±2)/中(9±2)/弱(11±2)，切换后 summary 段自动重写
- 左编辑右预览，工具栏：H1-H3、Bold/Italic、列表、表格、代码块、自定义"实施例块"
- 操作：[← 重新生成本节] [复制 markdown] [导出 docx (占位)] [提交 IP 部门]
- "导出 docx"：toast"v0.2 支持，已下载占位 .docx 文件"
- "提交 IP 部门" → 调 mock POST `/api/projects/:id/submit`，状态变 `submitted`

### 6.5 Reviewer 审阅页

- 项目元信息条（提交人/部门/时间/结论）
- 主区交底书内容（只读）+ 右侧批注侧栏
- 批注高亮原文段落（hover 气泡，点击高亮+滚动）
- 底部操作：[退回补充] [拒绝] [批准 ✓]
- 提交后 toast"已通知员工"

### 6.6 RBAC 路由守卫

```ts
router.beforeEach((to, from, next) => {
  const auth = useAuthStore();
  if (to.path === '/patent/login') return next();
  if (!auth.user) return next('/patent/login');
  const allow = RBAC[auth.user.role].some(r => r.test(to.path));
  if (!allow) return next('/patent/403');
  next();
});
```

### 6.7 Pinia stores

| store | 持久化 | 用途 |
|---|---|---|
| `useAuthStore` | localStorage | 当前 user + role |
| `useProjectStore` | sessionStorage | 项目列表/当前项目 |
| `useChatStore` | 内存 | 当前 mining 流 |
| `useUIStore` | localStorage | 主题、菜单折叠 |

### 6.8 错误/空态/loading

- 空态用 Soybean 内置 empty 组件，配主 CTA
- 列表骨架屏；流式对话打字机 cursor `|`
- 保留 axios 全局拦截器（占位，将来接真后端用）

## 7. 部署到 `blind.pub/patent`

### 7.1 Vite 配置

```ts
// vite.config.ts
export default defineConfig(({ mode }) => ({
  base: '/patent/',
  build: { outDir: 'dist', sourcemap: mode === 'staging', chunkSizeWarningLimit: 1500 },
  resolve: { alias: { '@': resolve(__dirname, 'src') } },
  plugins: [vue()],
}));
```

```ts
// router/index.ts
const router = createRouter({ history: createWebHistory('/patent/'), routes });
```

### 7.2 MSW 在生产构建里也启用

```ts
// main.ts
if (import.meta.env.MODE !== 'test') {
  const { worker } = await import('./mock/browser');
  await worker.start({
    serviceWorker: { url: '/patent/mockServiceWorker.js' },
    onUnhandledRequest: 'bypass',
  });
}
```

`public/mockServiceWorker.js` 由 `npx msw init public/` 生成；vite 复制到 `dist/`。

### 7.3 Nginx 增量配置

追加到 `/etc/nginx/conf.d/3xui.conf` 的 `server { server_name blind.pub; ... }` 块：

```nginx
location = /patent {
    return 301 /patent/;
}

location /patent/ {
    alias /var/www/patent/;
    index index.html;
    try_files $uri $uri/ /patent/index.html;

    location ~ ^/patent/mockServiceWorker\.js$ {
        alias /var/www/patent/mockServiceWorker.js;
        types { } default_type application/javascript;
        add_header Service-Worker-Allowed "/patent/";
    }

    location ~* /patent/.*\.(js|css|png|jpg|svg|woff2)$ {
        alias /var/www/patent/$1;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    add_header Cache-Control "no-cache, no-store, must-revalidate";
    add_header X-Robots-Tag "noindex, nofollow";
}
```

### 7.4 部署脚本

```json
// package.json
{
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview --base /patent/",
    "deploy": "pnpm run build && bash scripts/deploy.sh"
  }
}
```

```bash
# scripts/deploy.sh
#!/usr/bin/env bash
set -euo pipefail
DIST=dist; TARGET=/var/www/patent
sudo mkdir -p "$TARGET"
sudo rsync -av --delete "$DIST/" "$TARGET/"
sudo nginx -t && sudo nginx -s reload
echo "✓ deployed to https://blind.pub/patent/"
```

### 7.5 自检脚本

```bash
curl -I https://blind.pub/patent/
curl -I https://blind.pub/patent/mockServiceWorker.js   # 应 application/javascript
curl -sS https://blind.pub/patent/ | grep -c '<div id="app"'  # >= 1
```

### 7.6 SEO/收录控制

`<head>` 加 `<meta name="robots" content="noindex,nofollow">` + nginx 加 `X-Robots-Tag: noindex`，避免原型被搜索引擎收录。

## 8. 风险与已知踩坑

| 风险 | 对策 |
|---|---|
| MSW worker 在 history 路由下被 fallback 拦走 | nginx 把 `/patent/mockServiceWorker.js` 单独 alias，**先匹配** |
| 部署后浏览器缓存了旧 SW | 部署脚本不缓存 `mockServiceWorker.js`，README 注明首访强刷 |
| nginx `alias` 与 `try_files` 同时使用语法陷阱 | 用 `$uri/ /patent/index.html` 模式 |
| Soybean Admin 默认带 vite-plugin-mock 冲突 | 装项目时关掉它内置 mock，只用我们的 MSW |
| 中文字符路径 / 文件名导致 nginx 404 | dist 内全是 hash 化英文资源名，无影响 |
| 原型公网域被搜索引擎收录 | meta robots + X-Robots-Tag 双重防护 |
| 流式 SSE 在 nginx 反代被 buffer | 这次部署是静态 alias，不涉及反代；未来接真后端再注意 `proxy_buffering off` |

## 9. 验收

- [ ] 三个 demo case 全跑通：员工 → 报门 → mining(伪流式) → search(4 档结论 + 文献表) → disclosure(三档独权切换 + Tiptap) → submit
- [ ] 流式对话视感与真 LLM 流式无明显差异
- [ ] reviewer 角色：能看到密码学 case 待审、信息安全 case 已通过、AI case 退回；能批注、改状态
- [ ] admin 角色：能看到 3 个项目分布的饼图和 reviewer 流转
- [ ] 三种角色一键切换，受 RBAC 路由守卫保护，越权跳 403
- [ ] 部署 `https://blind.pub/patent/` 可访问，刷新不 404
- [ ] MSW worker 注册成功（DevTools Application / Service Workers 看见）
- [ ] 移动端简单适配（Soybean 默认）

## 10. 后续路线

- v0.1（本 spec）：MSW mid-fi 原型 + 三 case + 部署
- v0.2：导出 docx 真实现 + i18n 切换 + 更多 case 上传/编辑
- v0.5：接真后端（FastAPI Best Architecture），换 axios baseURL 即可，业务代码不动
- v0.7：接真智慧芽 adapter（HIP cookie+playwright）
- v1.0：完整 v2 多子系统集成
