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

// v0.34: detached agent runs
export interface AgentRun {
  id: string;
  project_id: string | null;
  endpoint: string;
  status: 'running' | 'completed' | 'error' | 'cancelled';
  idea: string | null;
  started_at: string | null;
  finished_at: string | null;
  total_cost_usd: number | null;
  num_turns: number | null;
  error: string | null;
}

export interface AgentEventRow {
  seq: number;
  type: string;
  payload: Record<string, unknown>;
  created_at: string | null;
}

export interface StartRunBody {
  endpoint: 'mine_spike' | 'mine_full';
  project_id?: string;
  idea: string;
  max_turns?: number;
  sections?: string[];
}

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

  /** v0.21: agent SDK 一键全程挖掘 — 串跑 5 节 (prior_art / summary / embodiments / claims / drawings_description) */
  mineFullStream(projectId: string, idea: string, onEvent: (e: ChatStreamEvent) => void,
                 signal?: AbortSignal): Promise<void> {
    return consumeSSE(`/api/agent/mine_full/${projectId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idea }),
    }, onEvent, signal);
  },

  /**
   * v0.34: detached agent runs — 客户端断开不影响后端 task 跑完，
   * 重新打开页面 SSE tail since=last_seq 即可恢复显示。
   */
  agentRuns: {
    async start(body: StartRunBody): Promise<{ run_id: string }> {
      const r = await fetch('/api/agent/runs/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`start run failed: ${r.status} ${await r.text()}`);
      return r.json();
    },

    async active(projectId: string): Promise<AgentRun | null> {
      const r = await fetch(`/api/agent/runs/active?project_id=${encodeURIComponent(projectId)}`);
      if (!r.ok) throw new Error(`active run lookup failed: ${r.status}`);
      const txt = await r.text();
      if (!txt || txt === 'null') return null;
      return JSON.parse(txt) as AgentRun;
    },

    async get(runId: string): Promise<AgentRun> {
      const r = await fetch(`/api/agent/runs/${encodeURIComponent(runId)}`);
      if (!r.ok) throw new Error(`get run failed: ${r.status}`);
      return r.json();
    },

    async events(runId: string, since = 0): Promise<AgentEventRow[]> {
      const r = await fetch(`/api/agent/runs/${encodeURIComponent(runId)}/events?since=${since}`);
      if (!r.ok) throw new Error(`get events failed: ${r.status}`);
      return r.json();
    },

    async cancel(runId: string): Promise<{ ok: boolean; status: string }> {
      const r = await fetch(`/api/agent/runs/${encodeURIComponent(runId)}/cancel`, { method: 'POST' });
      if (!r.ok) throw new Error(`cancel failed: ${r.status}`);
      return r.json();
    },

    /** SSE tail：since=N 起拉历史 events 后实时跟进。 */
    stream(runId: string, since: number,
           onEvent: (e: ChatStreamEvent) => void,
           signal?: AbortSignal): Promise<void> {
      return consumeSSE(
        `/api/agent/runs/${encodeURIComponent(runId)}/stream?since=${since}`,
        { method: 'GET' },
        onEvent,
        signal,
      );
    },
  },
};
