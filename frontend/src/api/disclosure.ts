import { apiClient } from './client';
import type { Disclosure, ClaimTier, FileNode } from '@/types';

export interface GenerateDocxResponse {
  ok: boolean;
  file: FileNode;
  projectStatus?: string;
}

export const disclosureApi = {
  get: (projectId: string) =>
    apiClient.get<Disclosure>(`/projects/${projectId}/disclosure`).then(r => r.data),
  save: (projectId: string, body: Partial<Disclosure>) =>
    apiClient.put<Disclosure>(`/projects/${projectId}/disclosure`, body).then(r => r.data),
  selectClaimTier: (projectId: string, tier: ClaimTier) =>
    apiClient.post<Disclosure>(`/projects/${projectId}/disclosure/claim-tier`, { tier }).then(r => r.data),
  /** v0.7-B 后端真生成 .docx 落到 AI 输出/，返回 {ok, file: FileNode, projectStatus?} */
  generateDocx: (projectId: string) =>
    apiClient.post<GenerateDocxResponse>(`/projects/${projectId}/disclosure/docx`).then(r => r.data),
};
