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

  it('attach 持久化 + 恢复对话历史', () => {
    sessionStorage.clear();
    const a = useChatStore();
    a.attach('p-1');
    a.appendUser('问题1');
    a.startAgent();
    a.appendDelta('回答1');
    a.endAgent();
    a.applyFields(['领域:AI']);

    // 模拟刷新：换 pinia 实例从 sessionStorage 恢复
    setActivePinia(createPinia());
    const b = useChatStore();
    b.attach('p-1');
    expect(b.messages).toHaveLength(2);
    expect(b.messages[0].content).toBe('问题1');
    expect(b.messages[1].content).toBe('回答1');
    expect(b.capturedFields).toEqual(['领域:AI']);
    expect(b.streaming).toBe(false); // 不持久化 streaming
  });

  // v0.18-C 结构化卡片
  it('appendToolCall + attachToolResult 把 result 挂到最近 tool_call', () => {
    const s = useChatStore();
    s.appendToolCall('search_patents', { kw: 'AI' }, 'tu_1');
    expect(s.messages).toHaveLength(1);
    expect(s.messages[0].type).toBe('tool_call');
    expect(s.messages[0].tool?.name).toBe('search_patents');
    expect(s.messages[0].tool?.result).toBeUndefined();

    s.attachToolResult('found 3 hits', { hits: 3 });
    expect(s.messages[0].tool?.result).toBe('found 3 hits');
    expect(s.messages[0].tool?.data).toEqual({ hits: 3 });
  });

  it('appendThinking / appendError 推独立卡片消息', () => {
    const s = useChatStore();
    s.appendThinking('想想看…');
    s.appendError('boom');
    expect(s.messages).toHaveLength(2);
    expect(s.messages[0].type).toBe('thinking');
    expect(s.messages[0].content).toBe('想想看…');
    expect(s.messages[1].type).toBe('error');
    expect(s.messages[1].content).toBe('boom');
  });

  it('attach 老数据无 type 字段 → 兜底 text', () => {
    sessionStorage.clear();
    sessionStorage.setItem('pp.chat.p-legacy', JSON.stringify({
      messages: [{ id: 'm1', role: 'user', content: 'old', ts: '2024-01-01' }],
      capturedFields: [],
    }));
    const s = useChatStore();
    s.attach('p-legacy');
    expect(s.messages[0].type).toBe('text');
    expect(s.messages[0].content).toBe('old');
  });

  // v0.20 Wave1: section 进度
  it('sectionProgress 初始 5 个 pending；setSectionStatus 切到 running/done', () => {
    const s = useChatStore();
    expect(s.sectionProgress.prior_art).toBe('pending');
    expect(s.sectionProgress.summary).toBe('pending');
    expect(s.sectionProgress.embodiments).toBe('pending');
    expect(s.sectionProgress.claims).toBe('pending');
    expect(s.sectionProgress.drawings_description).toBe('pending');

    s.setSectionStatus('prior_art', 'running');
    expect(s.sectionProgress.prior_art).toBe('running');

    s.setSectionStatus('prior_art', 'done');
    expect(s.sectionProgress.prior_art).toBe('done');

    s.resetSectionProgress();
    expect(s.sectionProgress.prior_art).toBe('pending');
  });

  // v0.20 Wave1: tool_call 耗时
  it('attachToolResult 计算 tDurationMs（>=0）', async () => {
    const s = useChatStore();
    s.appendToolCall('search_patents', { kw: 'AI' });
    expect(s.messages[0].tool?.t0).toBeTypeOf('number');
    // 强制 tick 一下时间
    await new Promise(r => setTimeout(r, 5));
    s.attachToolResult('ok');
    expect(s.messages[0].tool?.tDurationMs).toBeTypeOf('number');
    expect(s.messages[0].tool!.tDurationMs!).toBeGreaterThanOrEqual(0);
  });

  it('attach 不同 projectId 隔离', () => {
    sessionStorage.clear();
    const a = useChatStore();
    a.attach('p-1');
    a.appendUser('A 项目');

    setActivePinia(createPinia());
    const b = useChatStore();
    b.attach('p-2');
    expect(b.messages).toEqual([]);
  });
});
