/**
 * v0.35 关键回归测试：chat store 流式能力。
 * 直接复现 v0.34 用户反馈的「报门后空气泡 + 卡死光标」bug：
 *   - mount 一个 minimal 组件订阅 store.messages[0].content
 *   - 让 store.appendDelta 跑，断言 DOM 是否实时更新
 *
 * 还覆盖：
 *   - appendDelta 找不到 text agent 时兜底 push（v0.34.4）
 *   - attach() 清空 stale 空 agent 残留（v0.34.3）
 *   - streaming 卡死自愈（v0.34.4）
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { defineComponent, h, computed } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import { useChatStore } from '@/stores/chat';

// 简易 reactive 探针组件 —— 把 store.messages[0].content 渲染到 DOM
const ChatProbe = defineComponent({
  setup() {
    const chat = useChatStore();
    const first = computed(() => chat.messages[0]?.content ?? '<empty>');
    const lastNonEmpty = computed(() => {
      // 用于「找不到 text agent 兜底」场景：测最后一条非空 content
      for (let i = chat.messages.length - 1; i >= 0; i--) {
        if (chat.messages[i].content) return chat.messages[i].content;
      }
      return '<empty>';
    });
    return () => h('div', { class: 'probe' }, [
      h('span', { class: 'first' }, first.value),
      h('span', { class: 'last' }, lastNonEmpty.value),
      h('span', { class: 'count' }, String(chat.messages.length)),
    ]);
  },
});

describe('chat store streaming reactivity (v0.34 bug regression)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    setActivePinia(createPinia());
  });

  describe('appendDelta DOM 反应（核心防回归 — 报门空气泡 bug）', () => {
    it('startAgent → appendDelta(hello) → DOM 立刻含 hello', async () => {
      const wrapper = mount(ChatProbe);
      const chat = useChatStore();

      chat.startAgent();
      await flushPromises();
      expect(wrapper.find('.first').text()).toBe(''); // 空气泡刚 push
      expect(wrapper.find('.count').text()).toBe('1');

      chat.appendDelta('hello');
      await flushPromises();
      expect(wrapper.find('.first').text()).toBe('hello');
    });

    it('多次 appendDelta 累计 helloworld（reactive trigger 不能丢）', async () => {
      const wrapper = mount(ChatProbe);
      const chat = useChatStore();

      chat.startAgent();
      chat.appendDelta('hello');
      chat.appendDelta('world');
      await flushPromises();
      expect(wrapper.find('.first').text()).toBe('helloworld');
      // 确认 messages 数组没意外膨胀（应该还是 1 条 agent 气泡）
      expect(chat.messages).toHaveLength(1);
      expect(chat.messages[0].content).toBe('helloworld');
    });

    it('中文 delta 多次累计也能 reactive 更新', async () => {
      const wrapper = mount(ChatProbe);
      const chat = useChatStore();
      chat.startAgent();
      ['你', '好', '世', '界'].forEach(c => chat.appendDelta(c));
      await flushPromises();
      expect(wrapper.find('.first').text()).toBe('你好世界');
    });
  });

  describe('appendDelta 找不到 text agent 时兜底 push（v0.34.4）', () => {
    it('reset 不调 startAgent → appendDelta 自动 push 一条 agent text bubble', async () => {
      const chat = useChatStore();
      chat.reset();
      expect(chat.messages).toHaveLength(0);

      chat.appendDelta('orphan delta');
      expect(chat.messages).toHaveLength(1);
      expect(chat.messages[0].role).toBe('agent');
      expect(chat.messages[0].type).toBe('text');
      expect(chat.messages[0].content).toBe('orphan delta');
    });

    it('SSE 抢先于 startAgent — 先 appendDelta 再 startAgent，两条独立 bubble', async () => {
      const chat = useChatStore();
      chat.appendDelta('first');
      chat.startAgent();
      chat.appendDelta('second');
      // 兜底 push 1 条 + startAgent push 1 条空 + 第二个 delta 写到 startAgent 那条 = 2 条
      expect(chat.messages).toHaveLength(2);
      expect(chat.messages[0].content).toBe('first');
      expect(chat.messages[1].content).toBe('second');
    });

    it('中间夹 tool_call/thinking 时 appendDelta 找最近 text agent，不 push 新 bubble', () => {
      const chat = useChatStore();
      chat.startAgent();          // text agent 0
      chat.appendThinking('think'); // thinking 1
      chat.appendToolCall('foo', {}); // tool_call 2
      chat.appendDelta('payload');
      // 不 push 新 bubble，写回 index 0 那条 text agent
      expect(chat.messages).toHaveLength(3);
      expect(chat.messages[0].content).toBe('payload');
    });
  });

  describe('attach() 清空 stale 空 agent 残留（v0.34.3）', () => {
    it('sessionStorage cached: messages 末尾有空 text agent → attach 后被清掉', () => {
      sessionStorage.setItem('pp.chat.p-stale', JSON.stringify({
        messages: [{ id: 'm1', role: 'agent', content: '', ts: '2026-05-09', type: 'text' }],
        capturedFields: [],
      }));
      const chat = useChatStore();
      chat.attach('p-stale');
      expect(chat.messages).toHaveLength(0);
    });

    it('多个连续空 agent 都被清掉（while loop 验证）', () => {
      sessionStorage.setItem('pp.chat.p-multi-stale', JSON.stringify({
        messages: [
          { id: 'u1', role: 'user', content: 'real msg', ts: 't', type: 'text' },
          { id: 'a1', role: 'agent', content: '', ts: 't', type: 'text' },
          { id: 'a2', role: 'agent', content: '   ', ts: 't', type: 'text' }, // 空白也算空
        ],
        capturedFields: [],
      }));
      const chat = useChatStore();
      chat.attach('p-multi-stale');
      expect(chat.messages).toHaveLength(1);
      expect(chat.messages[0].content).toBe('real msg');
    });

    it('末尾是非空 agent → 不动', () => {
      sessionStorage.setItem('pp.chat.p-real', JSON.stringify({
        messages: [
          { id: 'a1', role: 'agent', content: 'real reply', ts: 't', type: 'text' },
        ],
        capturedFields: [],
      }));
      const chat = useChatStore();
      chat.attach('p-real');
      expect(chat.messages).toHaveLength(1);
      expect(chat.messages[0].content).toBe('real reply');
    });

    it('末尾是 user → 不动（只清 agent text 空气泡）', () => {
      sessionStorage.setItem('pp.chat.p-user-tail', JSON.stringify({
        messages: [
          { id: 'u1', role: 'user', content: 'hi', ts: 't', type: 'text' },
        ],
        capturedFields: [],
      }));
      const chat = useChatStore();
      chat.attach('p-user-tail');
      expect(chat.messages).toHaveLength(1);
    });

    it('attach 流程不持久化 streaming（v0.18 历史保护）', () => {
      sessionStorage.setItem('pp.chat.p-stream', JSON.stringify({
        messages: [{ id: 'a1', role: 'agent', content: 'done', ts: 't', type: 'text' }],
        capturedFields: [],
      }));
      const chat = useChatStore();
      chat.attach('p-stream');
      expect(chat.streaming).toBe(false);
    });
  });

  describe('streaming 卡死自愈（v0.34.4）', () => {
    it('手动 set streaming=true 后调 endAgent → streaming=false', () => {
      const chat = useChatStore();
      chat.startAgent();
      expect(chat.streaming).toBe(true);
      chat.endAgent();
      expect(chat.streaming).toBe(false);
    });

    it('attach 重新进入工作台时 streaming 强制 false（避免刷新卡转圈）', () => {
      // 先做一轮：start + delta，但不调 endAgent（模拟 SSE 中断）
      const a = useChatStore();
      a.attach('p-resume');
      a.startAgent();
      a.appendDelta('partial');
      expect(a.streaming).toBe(true);

      // 模拟刷新（新 pinia 实例）
      setActivePinia(createPinia());
      const b = useChatStore();
      b.attach('p-resume');
      expect(b.streaming).toBe(false);
    });
  });

  describe('detached run id 持久化（v0.34）', () => {
    it('setCurrentRun 后 attach 同 projectId 能恢复 currentRunId', () => {
      const a = useChatStore();
      a.attach('p-detached');
      a.setCurrentRun('r-test-1');
      a.bumpLastSeq(5);

      setActivePinia(createPinia());
      const b = useChatStore();
      b.attach('p-detached');
      expect(b.currentRunId).toBe('r-test-1');
      // bumpLastSeq 节流：5 还没到 10 就不持久化，所以新实例 lastEventSeq=0
      // 但 setCurrentRun 时立刻 persist —— 这时 lastEventSeq 是 0，所以恢复也是 0
      expect(b.lastEventSeq).toBe(0);
    });

    it('setCurrentRun(null) 复位 lastEventSeq', () => {
      const chat = useChatStore();
      chat.attach('p-reset');
      chat.bumpLastSeq(20); // 触发 persist
      chat.setCurrentRun(null);
      expect(chat.currentRunId).toBeNull();
      expect(chat.lastEventSeq).toBe(0);
    });
  });
});
