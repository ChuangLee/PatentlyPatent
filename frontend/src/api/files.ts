import { apiClient } from './client';
import type { FileNode } from '@/types';

export const filesApi = {
  create: (pid: string, body: Partial<FileNode>) =>
    apiClient.post<FileNode>(`/projects/${pid}/files`, body).then(r => r.data),
  update: (pid: string, fid: string, body: Partial<FileNode>) =>
    apiClient.patch<FileNode>(`/projects/${pid}/files/${fid}`, body).then(r => r.data),

  /** v0.32: multipart 上传 binary（pdf / office / 图片 等） */
  upload: (pid: string, file: File, parentId: string | null, source = 'user') => {
    const fd = new FormData();
    fd.append('file', file);
    if (parentId) fd.append('parentId', parentId);
    fd.append('source', source);
    return apiClient.post<FileNode>(`/projects/${pid}/files/upload`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data);
  },

  /** v0.32: 下载 / inline 预览 URL（pdf iframe / 图片 img / 其他下载） */
  downloadUrl: (pid: string, fid: string): string =>
    `/patent/api/projects/${pid}/files/${fid}/download`,
};
