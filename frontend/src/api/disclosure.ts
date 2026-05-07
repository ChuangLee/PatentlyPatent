import { apiClient } from './client';
import type { Disclosure, ClaimTier } from '@/types';

export const disclosureApi = {
  get: (projectId: string) =>
    apiClient.get<Disclosure>(`/projects/${projectId}/disclosure`).then(r => r.data),
  save: (projectId: string, body: Partial<Disclosure>) =>
    apiClient.put<Disclosure>(`/projects/${projectId}/disclosure`, body).then(r => r.data),
  selectClaimTier: (projectId: string, tier: ClaimTier) =>
    apiClient.post<Disclosure>(`/projects/${projectId}/disclosure/claim-tier`, { tier }).then(r => r.data),
};
