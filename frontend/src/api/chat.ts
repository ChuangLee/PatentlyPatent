import type { ChatStreamEvent } from '@/types';
import { consumeSSE } from '@/utils/sse';

export type AutoMineCtx = {
  title?: string;
  domain?: string;
  customDomain?: string;
  description?: string;
  intake?: { stage: string; goal: string; notes?: string };
  aiRootId?: string;
};

export const chatApi = {
  /** 发一轮对话，回调每个 SSE 事件 */
  stream(projectId: string, round: number, userMsg: string,
         onEvent: (e: ChatStreamEvent) => void,
         signal?: AbortSignal): Promise<void> {
    return consumeSSE(`/api/projects/${projectId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ round, userMsg }),
    }, onEvent, signal);
  },

  /** 进入工作台时自动触发：AI 自己挖掘 */
  autoMine(projectId: string, ctx: AutoMineCtx, onEvent: (e: ChatStreamEvent) => void,
           signal?: AbortSignal): Promise<void> {
    return consumeSSE(`/api/projects/${projectId}/auto-mining`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ctx),
    }, onEvent, signal);
  },

  /** v0.17-D: agent SDK spike 路径（admin toggle 用） */
  agentMineSpike(idea: string, onEvent: (e: ChatStreamEvent) => void,
                 signal?: AbortSignal, maxTurns = 8): Promise<void> {
    return consumeSSE(`/api/agent/mine_spike`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idea, max_turns: maxTurns }),
    }, onEvent, signal);
  },
};
