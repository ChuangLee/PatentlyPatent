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

  /** 进入工作台时自动触发：AI 自己挖掘，能填的填好（spawn 文件），剩余列问题清单 */
  autoMine(projectId: string, ctx: {
    title?: string;
    domain?: string;
    customDomain?: string;
    description?: string;
    intake?: { stage: string; goal: string; notes?: string };
    aiRootId?: string;
  }, onEvent: (e: ChatStreamEvent) => void): Promise<void> {
    return consumeSSE(`/api/projects/${projectId}/auto-mining`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ctx),
    }, onEvent);
  },
};
