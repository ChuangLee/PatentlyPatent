import type { ChatStreamEvent } from '@/types';

/** 用 fetch + ReadableStream 消费 SSE，逐事件回调。
 *  支持事件格式：`event: <type>\ndata: <json>\n\n`
 */
export async function consumeSSE(
  url: string,
  init: RequestInit,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const res = await fetch(url, { ...init, signal });
    if (!res.body) throw new Error('SSE: response has no body');

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // v0.35 fix: SSE 标准 spec 用 \r\n\r\n 或 \n\n 分隔事件（sse-starlette 用 CRLF）
      // 之前只 split('\n\n') 导致 CRLF 时 buffer 永远累积，0 个 event 被解析
      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop() ?? '';
      for (const block of events) {
        const ev = parseSSEBlock(block);
        if (ev) onEvent(ev);
      }
    }
  } catch (err: any) {
    // 用户主动 abort：静默返回，不抛错
    if (err?.name === 'AbortError') return;
    throw err;
  }
}

function parseSSEBlock(block: string): ChatStreamEvent | null {
  // v0.35 fix: 支持 CRLF 行内分隔
  const lines = block.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  let type = '';
  let data = '';
  for (const line of lines) {
    if (line.startsWith('event:')) type = line.slice(6).trim();
    else if (line.startsWith('data:')) data = line.slice(5).trim();
  }
  if (!type) return null;
  let parsed: any = {};
  try { parsed = data ? JSON.parse(data) : {}; } catch { /* keep parsed={} */ }
  // 已知 typed event：保留原结构（向后兼容）
  if (type === 'thinking') {
    if (parsed && typeof parsed.text === 'string') return { type: 'thinking', text: parsed.text } as any;
    return { type: 'thinking' };
  }
  if (type === 'done') return { type: 'done', ...parsed };
  if (type === 'delta' && typeof parsed.chunk === 'string')
    return { type: 'delta', chunk: parsed.chunk };
  // v0.20: agent_sdk 路径的 delta 用 text 字段
  if (type === 'delta' && typeof parsed.text === 'string')
    return { type: 'delta', chunk: parsed.text } as any;
  if (type === 'fields' && Array.isArray(parsed.captured))
    return { type: 'fields', captured: parsed.captured };
  // v0.34: 透传所有未知事件（tool_use/tool_result/file/error/section_start/section_done/stream_end…）
  // 把 SSE event 名作为 type，data 内字段直接附上
  return { type, ...parsed } as any;
}
