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
