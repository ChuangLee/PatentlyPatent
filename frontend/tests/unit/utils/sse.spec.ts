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
