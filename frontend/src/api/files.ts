import { apiClient } from './client';
import type { FileNode } from '@/types';

export const filesApi = {
  create: (pid: string, body: Partial<FileNode>) =>
    apiClient.post<FileNode>(`/projects/${pid}/files`, body).then(r => r.data),
  update: (pid: string, fid: string, body: Partial<FileNode>) =>
    apiClient.patch<FileNode>(`/projects/${pid}/files/${fid}`, body).then(r => r.data),
};
