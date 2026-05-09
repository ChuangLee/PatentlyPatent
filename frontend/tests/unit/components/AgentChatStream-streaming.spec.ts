/**
 * v0.35 AgentChatStream 端到端组件测试
 *
 * 关键 user journey：
 *   报门 → 工作台 → autoMine → SSE delta → chat.appendDelta → bubble 渲染
 *
 * 直接复现 v0.34 用户反馈：「报门后 chat 显示空气泡 + cursor 卡住，永远不渲染 SSE 内容」
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import AgentChatStream from '@/components/chat/AgentChatStream.vue';
import { useChatStore } from '@/stores/chat';
import { useUIStore } from '@/stores/ui';
import { mockFetchSSE, makeSSEStream } from '../../helpers/sse-mock';

// 把 chatApi.agentRuns.start/get/cancel/events 这些走 axios 的接口 mock 成函数级别，
// 这样我们能直接控制返回值而不需要依赖 happy-dom 的 fetch + axios http adapter
const agentRunsState = {
  startResp: { run_id: 'r-test' } as { run_id: string } | Error,
  status: 'completed' as 'running' | 'completed' | 'error' | 'cancelled',
  events: [] as Array<{ seq: number; type: string; payload: any; created_at: string | null }>,
};

vi.mock('@/api/chat', async (importOriginal) => {
  const orig = await importOriginal<typeof import('@/api/chat')>();
  return {
    ...orig,
    chatApi: {
      ...orig.chatApi,
      agentRuns: {
        ...orig.chatApi.agentRuns,
        start: vi.fn(async () => {
          if (agentRunsState.startResp instanceof Error) throw agentRunsState.startResp;
          return agentRunsState.startResp;
        }),
        get: vi.fn(async (runId: string) => ({
          id: runId,
          project_id: 'p-test',
          endpoint: 'mine_full',
          status: agentRunsState.status,
          idea: '',
          started_at: null,
          finished_at: null,
          total_cost_usd: null,
          num_turns: null,
          error: null,
        })),
        events: vi.fn(async () => agentRunsState.events),
        cancel: vi.fn(async () => ({ ok: true, status: 'cancelled' })),
        active: vi.fn(async () => null),
        stream: orig.chatApi.agentRuns.stream, // 保留真实 SSE consumer，走 mock fetch
      },
    },
  };
});

// stub heavy antd components；只跑 chat-stream 内 reactive 渲染逻辑
const STUBS = {
  'a-button': { template: '<button><slot /></button>' },
  'a-input': { template: '<input />' },
  Button: { template: '<button><slot /></button>' },
  Input: { template: '<input />' },
  Segmented: { template: '<div />' },
  Collapse: { template: '<div><slot /></div>' },
  CollapsePanel: { template: '<div><slot /></div>' },
  Spin: { template: '<span />' },
};

function mountChat(projectId = 'p-test', round = 1) {
  return mount(AgentChatStream, {
    props: { projectId, round },
    global: {
      plugins: [createPinia()],
      stubs: STUBS,
    },
  });
}

describe('AgentChatStream user journey (v0.34 卡空气泡 bug 复现 + 防回归)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    setActivePinia(createPinia());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('a) 报门→工作台→ SSE delta → bubble 渲染（mining 模式）', () => {
    it('autoMine 把 delta 累计渲染到 DOM（核心防回归）', async () => {
      mockFetchSSE([
        { event: 'thinking', data: { text: '思考中…' } },
        { event: 'delta', data: { chunk: '你' } },
        { event: 'delta', data: { chunk: '好' } },
        { event: 'done', data: {} },
      ]);

      const w = mountChat();
      const chat = useChatStore();
      const ui = useUIStore();
      ui.agentMode = 'mining'; // 走 autoMine 老路径

      // 公开的 autoMine 接口（defineExpose）
      await (w.vm as any).autoMine({ title: 'test', description: 'x', domain: 'ai' });
      await flushPromises();

      const text = w.text();
      // bubble 内容应包含 SSE delta 累计的 '你好'
      expect(text).toContain('你好');
      // done 事件触发 endAgent → streaming 应为 false
      expect(chat.streaming).toBe(false);
    });

    it('SSE 分包到达（buffer 拼接边界）也能正确渲染', async () => {
      mockFetchSSE(
        [
          { event: 'delta', data: { chunk: 'AB' } },
          { event: 'delta', data: { chunk: 'CD' } },
          { event: 'done', data: {} },
        ],
        { perChunk: 'half' },
      );

      const w = mountChat();
      const ui = useUIStore();
      ui.agentMode = 'mining';

      await (w.vm as any).autoMine({ title: 't', description: 'd', domain: 'ai' });
      await flushPromises();

      expect(w.text()).toContain('ABCD');
    });
  });

  describe('b) agent_sdk 模式走 detached run（v0.34 detached）', () => {
    it('autoMine → start 拿 run_id → SSE tail → DOM 出 delta', async () => {
      agentRunsState.startResp = { run_id: 'r-test' };
      agentRunsState.status = 'completed';
      // SSE stream（chatApi.agentRuns.stream 仍走真实 consumeSSE → 走全局 fetch）
      vi.spyOn(globalThis, 'fetch').mockImplementation(async () => makeSSEStream([
        { event: 'thinking', data: { text: '想…' } },
        { event: 'delta', data: { chunk: 'hello-' } },
        { event: 'delta', data: { chunk: 'detached' } },
        { event: 'stream_end', data: {} },
      ]));

      const w = mountChat('p-test', 1);
      const chat = useChatStore();
      const ui = useUIStore();
      ui.agentMode = 'agent_sdk';

      await (w.vm as any).autoMine({ title: 't', description: 'd', domain: 'ai' });
      await flushPromises();

      // SSE 期间 setCurrentRun('r-test')；finally 拉 status=completed → setCurrentRun(null)
      // 但渲染期间 currentRunId 应该确实被设过（中间状态）
      expect(w.text()).toContain('hello-detached');
      // streaming 收尾 stream_end → endAgent
      expect(chat.streaming).toBe(false);
    });

    it('start 失败 → appendError + endAgent（autoMine 内层 try/catch 吞 + antMessage 提示）', async () => {
      agentRunsState.startResp = new Error('boom');

      const w = mountChat();
      const chat = useChatStore();
      const ui = useUIStore();
      ui.agentMode = 'agent_sdk';

      // autoMine agent_sdk 分支自带 try/catch 包裹 startDetachedRun，外层不会抛
      await (w.vm as any).autoMine({ title: 't', description: 'd', domain: 'ai' });
      await flushPromises();

      // startDetachedRun 路径：catch 里 appendError('启动失败：boom') + endAgent
      const hasError = chat.messages.some(
        m => m.type === 'error' && m.content.includes('启动失败'),
      );
      expect(hasError).toBe(true);
      expect(chat.streaming).toBe(false);
    });
  });

  describe('c) 空 delta 边界（只 thinking + done）', () => {
    it('bubble content 留空但 streaming 收尾正确', async () => {
      mockFetchSSE([
        { event: 'thinking', data: { text: '想想…' } },
        { event: 'done', data: {} },
      ]);

      const w = mountChat();
      const chat = useChatStore();
      const ui = useUIStore();
      ui.agentMode = 'mining';

      await (w.vm as any).autoMine({ title: 't', description: 'd', domain: 'ai' });
      await flushPromises();

      // 没 delta —— text agent 气泡仍存在（startAgent 创建过）但 content=''
      const textAgent = chat.messages.find(m => m.role === 'agent' && (m.type ?? 'text') === 'text');
      expect(textAgent).toBeDefined();
      expect(textAgent!.content).toBe('');
      // thinking 卡片独立存在
      expect(chat.messages.some(m => m.type === 'thinking' && m.content === '想想…')).toBe(true);
      expect(chat.streaming).toBe(false);
    });
  });

  describe('d) 错误降级', () => {
    it('mining 模式 fetch 抛 NetworkError → autoMine 异常冒泡', async () => {
      // mining 路径里 autoMine 没有外层 try/catch，会冒泡（finally 只 reset currentAbort）
      vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
        throw new TypeError('NetworkError when attempting to fetch resource');
      });

      const w = mountChat();
      const ui = useUIStore();
      ui.agentMode = 'mining';

      let caught: unknown = null;
      try {
        await (w.vm as any).autoMine({ title: 't', description: 'd', domain: 'ai' });
      } catch (e) { caught = e; }
      await flushPromises();

      expect(caught).toBeInstanceOf(Error);
      // streaming 卡 true —— v0.34.4 已加自愈：下次 autoMine 进入会强制 endAgent
      // （自愈逻辑在 chat-streaming.spec 单元覆盖；此处只验异常冒泡）
    });
  });
});
