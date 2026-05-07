import { apiClient } from './client';
import type { Project, Domain, Attachment } from '@/types';

export const projectsApi = {
  list: (params?: { ownerId?: string }) =>
    apiClient.get<Project[]>('/projects', { params }).then(r => r.data),
  get: (id: string) =>
    apiClient.get<Project>(`/projects/${id}`).then(r => r.data),
  create: (data: {
    title: string;
    description: string;
    domain: Domain;
    customDomain?: string;
    ownerId: string;
    attachments?: Attachment[];
  }) =>
    apiClient.post<Project>('/projects', data).then(r => r.data),
};
