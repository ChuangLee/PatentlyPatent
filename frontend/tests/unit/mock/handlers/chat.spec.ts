// @vitest-environment node
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { chatHandlers } from '@/mock/handlers/chat';
import { chatApi } from '@/api/chat';
import type { ChatStreamEvent } from '@/types';

// node 环境下 fetch 不识别相对 URL（也没有 location），给 chatApi 用的相对路径包一层 base
// 同时也避免 happy-dom 下 Response.body 被预锁定（locked）的兼容问题。
const BASE = 'http://localhost';
// 让 msw 把 handler 中的相对路径 `/api/...` 解析到这一 origin 上
(globalThis as any).location = new URL(BASE + '/');

// 直接用 chatHandlers，不依赖 src/mock/handlers/index.ts（index.ts 由主 task 合并）
const server = setupServer(...chatHandlers);

let unwrap: (() => void) | null = null;

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
  // msw listen 会替换 globalThis.fetch — 在 listen 之后再做 base-URL 包装。
  const wrapped = globalThis.fetch;
  const wrapper: typeof fetch = (input: any, init?: RequestInit) => {
    if (typeof input === 'string' && input.startsWith('/')) {
      return wrapped(BASE + input, init);
    }
    return wrapped(input, init);
  };
  globalThis.fetch = wrapper;
  unwrap = () => { globalThis.fetch = wrapped; };
});
afterEach(() => server.resetHandlers());
afterAll(() => {
  unwrap?.();
  server.close();
});

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
