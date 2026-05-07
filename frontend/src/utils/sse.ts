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
