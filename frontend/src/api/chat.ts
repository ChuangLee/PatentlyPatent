import type { ChatStreamEvent } from '@/types';
import { consumeSSE } from '@/utils/sse';

export const chatApi = {
  /** 发一轮对话，回调每个 SSE 事件 */
  stream(projectId: string, round: number, userMsg: string,
         onEvent: (e: ChatStreamEvent) => void): Promise<void> {
    return consumeSSE(`/api/projects/${projectId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ round, userMsg }),
    }, onEvent);
  },
};
