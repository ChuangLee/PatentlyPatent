/**
 * v0.35 ProjectWorkbench onMounted 分支回归测试
 *
 * 验证不同 (project.status, agentRuns.active, sessionStorage.currentRunId, role) 组合下：
 *   - 是否调 chatRef.autoMine（mining 模式 fresh draft）
 *   - 是否调 chatRef.mineFull（agent_sdk 模式 fresh draft）
 *   - 是否调 chatRef.resumeRun（接管运行中 / 终态回放）
 *   - admin / completed 等是否禁止启动
 *
 * 实现策略：用 stub 替换 AgentChatStream 组件，stub 暴露同名 spy 方法供断言。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { defineComponent } from 'vue';
import { setActivePinia, createPinia } from 'pinia';
import { createRouter, createMemoryHistory } from 'vue-router';

// --- Mock 依赖 -----------------------------------------------------------

// projectsApi.get 返不同 status 项目（每 case 单独覆盖）
const projectsState = {
  status: 'drafting' as 'drafting' | 'researching' | 'reporting' | 'completed',
};

vi.mock('@/api/projects', () => ({
  projectsApi: {
    get: vi.fn(async (id: string) => ({
      id,
      title: 'Test Project',
      description: 'desc',
      domain: 'ai',
      status: projectsState.status,
      ownerId: 'u1',
      createdAt: '2026-01-01',
      updatedAt: '2026-01-01',
      attachments: [],
      intake: { stage: '创意', goal: '专利', notes: '' },
      miningSummary: undefined,
      fileTree: [],
    })),
  },
}));

// chatApi.agentRuns.active / get：控制是否接管运行中/回放终态
const agentState = {
  active: null as null | { id: string; status: 'running' | 'completed' | 'error' | 'cancelled' },
  getById: {} as Record<string, { id: string; status: string }>,
};

vi.mock('@/api/chat', () => ({
  chatApi: {
    agentRuns: {
      active: vi.fn(async () => agentState.active),
      get: vi.fn(async (rid: string) => agentState.getById[rid] ?? { id: rid, status: 'completed' }),
      events: vi.fn(async () => []),
      stream: vi.fn(async () => {}),
      cancel: vi.fn(async () => ({ ok: true, status: 'cancelled' })),
      start: vi.fn(async () => ({ run_id: 'r-new' })),
    },
    stream: vi.fn(),
    autoMine: vi.fn(),
  },
}));

vi.mock('@/api/disclosure', () => ({
  disclosureApi: { generateDocx: vi.fn() },
}));

// AgentChatStream stub —— 暴露 autoMine/mineFull/resumeRun spies
const chatRefSpies = {
  autoMine: vi.fn(async () => {}),
  mineFull: vi.fn(async () => {}),
  resumeRun: vi.fn(async () => {}),
};

vi.mock('@/components/chat/AgentChatStream.vue', () => ({
  default: defineComponent({
    name: 'AgentChatStreamStub',
    props: ['projectId', 'round'],
    setup(_props, { expose }) {
      expose({
        autoMine: chatRefSpies.autoMine,
        mineFull: chatRefSpies.mineFull,
        resumeRun: chatRefSpies.resumeRun,
      });
      return () => null;
    },
  }),
}));

vi.mock('@/components/workbench/FilePreviewer.vue', () => ({
  default: { template: '<div class="file-previewer-stub"/>' },
}));
vi.mock('@/components/chat/MiniChatView.vue', () => ({
  default: { template: '<div class="mini-chat-stub"/>' },
}));
vi.mock('@/components/common/ReadonlyBanner.vue', () => ({
  default: { template: '<div class="banner-stub"/>' },
}));

// 现在 import — vi.mock 已经 hoist 在前面
import ProjectWorkbench from '@/views/employee/ProjectWorkbench.vue';
import { useChatStore } from '@/stores/chat';
import { useUIStore } from '@/stores/ui';
import { useAuthStore } from '@/stores/auth';

// --- 工具 ---------------------------------------------------------------

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/employee/projects/:id', name: 'workbench', component: ProjectWorkbench },
    ],
  });
}

const ANTD_STUBS = {
  'a-page-header': { template: '<div><slot/><slot name="extra"/><slot name="footer"/></div>' },
  'a-steps': { template: '<div><slot/></div>' },
  'a-step': { template: '<div/>' },
  'a-button': { template: '<button><slot/></button>' },
};

async function mountWorkbench(role: 'employee' | 'admin' = 'employee') {
  const pinia = createPinia();
  setActivePinia(pinia);
  const router = makeRouter();
  router.push('/employee/projects/p-test');
  await router.isReady();

  // 注入 auth role
  const auth = useAuthStore();
  auth.user = {
    id: role === 'admin' ? 'admin-1' : 'u-1',
    name: role,
    role,
    department: 'eng',
  };

  const w = mount(ProjectWorkbench, {
    global: {
      plugins: [pinia, router],
      stubs: ANTD_STUBS,
    },
  });
  return w;
}

// --- 测试 ---------------------------------------------------------------

describe('ProjectWorkbench onMounted 分支', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    chatRefSpies.autoMine.mockClear();
    chatRefSpies.mineFull.mockClear();
    chatRefSpies.resumeRun.mockClear();
    projectsState.status = 'drafting';
    agentState.active = null;
    agentState.getById = {};
  });
  afterEach(() => { vi.clearAllMocks(); });

  it('a) fresh draft + mining 模式 → 自动 autoMine', async () => {
    projectsState.status = 'drafting';
    agentState.active = null;
    const w = await mountWorkbench('employee');
    const ui = useUIStore();
    ui.agentMode = 'mining';

    await flushPromises();
    // setTimeout 300ms 等 chat ref 挂载
    await new Promise(r => setTimeout(r, 350));
    await flushPromises();

    expect(chatRefSpies.autoMine).toHaveBeenCalledTimes(1);
    expect(chatRefSpies.mineFull).not.toHaveBeenCalled();
    expect(chatRefSpies.resumeRun).not.toHaveBeenCalled();
    w.unmount();
  });

  it('a2) fresh draft + agent_sdk 模式 → 自动 mineFull', async () => {
    projectsState.status = 'drafting';
    agentState.active = null;
    const w = await mountWorkbench('employee');
    const ui = useUIStore();
    ui.agentMode = 'agent_sdk';

    await flushPromises();
    await new Promise(r => setTimeout(r, 350));
    await flushPromises();

    expect(chatRefSpies.mineFull).toHaveBeenCalledTimes(1);
    expect(chatRefSpies.autoMine).not.toHaveBeenCalled();
    w.unmount();
  });

  it('b) 接管运行中 run（active=running）→ resumeRun(rid, 0)', async () => {
    projectsState.status = 'researching';
    agentState.active = { id: 'r-running', status: 'running' };

    const w = await mountWorkbench('employee');
    await flushPromises();
    // resumeRun 在 setTimeout(100ms) 内调
    await new Promise(r => setTimeout(r, 150));
    await flushPromises();

    expect(chatRefSpies.resumeRun).toHaveBeenCalledTimes(1);
    expect(chatRefSpies.resumeRun).toHaveBeenCalledWith('r-running', 0);
    expect(chatRefSpies.autoMine).not.toHaveBeenCalled();
    expect(chatRefSpies.mineFull).not.toHaveBeenCalled();
    w.unmount();
  });

  it('c) 回放终态 run（sessionStorage 有 currentRunId, active=null, run=completed）', async () => {
    projectsState.status = 'completed';
    agentState.active = null;
    agentState.getById = { 'r-done': { id: 'r-done', status: 'completed' } };
    // sessionStorage 预设 chat.currentRunId
    sessionStorage.setItem('pp.chat.p-test', JSON.stringify({
      messages: [],
      capturedFields: [],
      currentRunId: 'r-done',
      lastEventSeq: 0,
    }));

    const w = await mountWorkbench('employee');
    await flushPromises();
    await new Promise(r => setTimeout(r, 150));
    await flushPromises();

    expect(chatRefSpies.resumeRun).toHaveBeenCalledTimes(1);
    expect(chatRefSpies.resumeRun).toHaveBeenCalledWith('r-done', 0);
    expect(chatRefSpies.autoMine).not.toHaveBeenCalled();
    expect(chatRefSpies.mineFull).not.toHaveBeenCalled();
    w.unmount();
  });

  it('d) status=completed + 无 currentRunId → 不重启', async () => {
    projectsState.status = 'completed';
    agentState.active = null;
    // sessionStorage 不预设 currentRunId

    const w = await mountWorkbench('employee');
    await flushPromises();
    await new Promise(r => setTimeout(r, 350));
    await flushPromises();

    expect(chatRefSpies.autoMine).not.toHaveBeenCalled();
    expect(chatRefSpies.mineFull).not.toHaveBeenCalled();
    expect(chatRefSpies.resumeRun).not.toHaveBeenCalled();
    w.unmount();
  });

  it('e) admin 角色 isReadonly → 不启动 autoMine/mineFull/resumeRun', async () => {
    projectsState.status = 'drafting';
    agentState.active = { id: 'r-admin', status: 'running' }; // 即便有 active 也不接管

    const w = await mountWorkbench('admin');
    await flushPromises();
    await new Promise(r => setTimeout(r, 350));
    await flushPromises();

    expect(chatRefSpies.autoMine).not.toHaveBeenCalled();
    expect(chatRefSpies.mineFull).not.toHaveBeenCalled();
    // admin 模式下 active run 接管也跳过（onMounted 里 isReadonly 包了 if）
    expect(chatRefSpies.resumeRun).not.toHaveBeenCalled();
    w.unmount();
  });

  it('f) 已有 meaningful 历史对话 → 不重新 autoMine', async () => {
    projectsState.status = 'drafting';
    agentState.active = null;
    sessionStorage.setItem('pp.chat.p-test', JSON.stringify({
      messages: [
        { id: 'u1', role: 'user', content: 'hi', ts: 't', type: 'text' },
        { id: 'a1', role: 'agent', content: 'hello', ts: 't', type: 'text' },
      ],
      capturedFields: [],
    }));

    const w = await mountWorkbench('employee');
    const chat = useChatStore();
    await flushPromises();
    await new Promise(r => setTimeout(r, 350));
    await flushPromises();

    // hasMeaningfulContent=true → isFreshDraft=false → 不调 autoMine/mineFull
    expect(chatRefSpies.autoMine).not.toHaveBeenCalled();
    expect(chatRefSpies.mineFull).not.toHaveBeenCalled();
    expect(chat.messages.length).toBeGreaterThan(0);
    w.unmount();
  });
});
