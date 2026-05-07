import { apiClient } from './client';
import type { SearchReport } from '@/types';

export const searchApi = {
  run: (projectId: string) =>
    apiClient.post<SearchReport>(`/projects/${projectId}/search`).then(r => r.data),
};
