import type { Project } from '@/types';
import { CASE_CRYPTO } from './case_crypto';
import { CASE_INFOSEC } from './case_infosec';
import { CASE_AI } from './case_ai';

export const ALL_CASES: Project[] = [CASE_CRYPTO, CASE_INFOSEC, CASE_AI];

export function findCase(id: string): Project | undefined {
  return ALL_CASES.find(p => p.id === id);
}

/** 给某 case 取第 n 轮 agent 答复（用于 chat handler）。round 从 1 起 */
export function getCaseAgentScript(projectId: string, round: number): {
  text: string; capturedFields: string[];
} | null {
  const p = findCase(projectId);
  if (!p?.miningSummary) return null;
  const agentMsgs = p.miningSummary.conversation.filter(m => m.role === 'agent');
  const msg = agentMsgs[round - 1];
  if (!msg) return null;
  return {
    text: msg.content,
    capturedFields: msg.meta?.capturedFields ?? [],
  };
}
