import { apiClient } from './client';
import type { Project, Domain } from '@/types';

export const projectsApi = {
  list: (params?: { ownerId?: string }) =>
    apiClient.get<Project[]>('/projects', { params }).then(r => r.data),
  get: (id: string) =>
    apiClient.get<Project>(`/projects/${id}`).then(r => r.data),
  create: (data: { title: string; description: string; domain: Domain; ownerId: string }) =>
    apiClient.post<Project>('/projects', data).then(r => r.data),
  submit: (id: string) =>
    apiClient.post<Project>(`/projects/${id}/submit`).then(r => r.data),
  unsubmit: (id: string) =>
    apiClient.post<Project>(`/projects/${id}/unsubmit`).then(r => r.data),
};
