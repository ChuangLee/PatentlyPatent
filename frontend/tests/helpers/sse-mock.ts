/**
 * SSE mock helpers for vitest（v0.35）
 *
 * 用途：把一组业务事件打包成 SSE Response/分片，喂给 fetch() 让前端
 * `consumeSSE`（src/utils/sse.ts）正常解析。
 *
 * 业务事件格式约定：`{ event: string; data: any }`
 *   - event：SSE event 名（thinking / delta / tool_use / file / error / done / stream_end…）
 *   - data：会被 JSON.stringify 后写入 `data:` 行
 *
 * 输出 SSE 文本格式：
 *     event: <event>\n
 *     data: <json>\n
 *     \n
 */
import { vi, type MockInstance } from 'vitest';

export interface SSEEventLike {
  event: string;
  data?: unknown;
}

/** 把单个业务事件序列化为符合 SSE 协议的纯文本 block。 */
export function encodeSSEEvent(ev: SSEEventLike): string {
  const dataStr = ev.data === undefined ? '' : JSON.stringify(ev.data);
  return `event: ${ev.event}\ndata: ${dataStr}\n\n`;
}

/** 把多个业务事件序列化为单段 SSE 纯文本。 */
export function encodeSSEStream(events: SSEEventLike[]): string {
  return events.map(encodeSSEEvent).join('');
}

/**
 * 把一组业务事件分包成多个 Uint8Array chunk（默认每个 event 一包），
 * 用于测试 SSE 分包/buffer 拼接逻辑。
 */
export function makeSSEChunks(
  events: SSEEventLike[],
  opts: { perChunk?: 'event' | 'all' | 'half' } = {},
): Uint8Array[] {
  const mode = opts.perChunk ?? 'event';
  const enc = new TextEncoder();
  if (mode === 'all') {
    return [enc.encode(encodeSSEStream(events))];
  }
  if (mode === 'half') {
    // 把整段 SSE 文本切两半，故意切在事件中间，验证 buffer 拼接
    const text = encodeSSEStream(events);
    const mid = Math.floor(text.length / 2);
    return [enc.encode(text.slice(0, mid)), enc.encode(text.slice(mid))];
  }
  return events.map(ev => enc.encode(encodeSSEEvent(ev)));
}

/**
 * 构造一个 ReadableStream-backed Response，模拟 SSE 长连接。
 * 用法：vi.spyOn(globalThis, 'fetch').mockResolvedValue(makeSSEStream(events))
 */
export function makeSSEStream(
  events: SSEEventLike[],
  opts: { perChunk?: 'event' | 'all' | 'half' } = {},
): Response {
  const chunks = makeSSEChunks(events, opts);
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(c);
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
    },
  });
}

/**
 * spy 全局 fetch 并对所有调用返回同一段 SSE Response。
 * 返回 spy instance（可继续 mockImplementation 覆盖）。
 *
 * 注意：返回前每次都用一个**新的** Response（ReadableStream 只能 consume 一次），
 * 否则二次调用会拿到 already-locked stream。
 */
export function mockFetchSSE(
  events: SSEEventLike[],
  opts: { perChunk?: 'event' | 'all' | 'half' } = {},
): MockInstance {
  const spy = vi.spyOn(globalThis, 'fetch');
  spy.mockImplementation(async () => makeSSEStream(events, opts));
  return spy;
}

/**
 * spy 全局 fetch，按 URL 路由返不同 Response。
 *  - matchers: { urlPattern: stringSubstr | RegExp, response: () => Response | Promise<Response> }
 *  - 默认 fallthrough：throw `unmatched fetch URL: ${url}`
 */
export function mockFetchRoutes(
  matchers: Array<{ match: string | RegExp; respond: () => Response | Promise<Response> }>,
): MockInstance {
  const spy = vi.spyOn(globalThis, 'fetch');
  spy.mockImplementation(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string'
      ? input
      : (input instanceof URL ? input.toString() : (input as Request).url);
    for (const m of matchers) {
      const ok = typeof m.match === 'string' ? url.includes(m.match) : m.match.test(url);
      if (ok) return m.respond();
    }
    throw new Error(`[mockFetchRoutes] unmatched fetch URL: ${url}`);
  });
  return spy;
}

/** 便利构造：JSON Response（用于 axios apiClient 路径） */
export function makeJsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
