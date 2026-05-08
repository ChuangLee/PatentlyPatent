import { apiClient } from './client';
import type { FileNode } from '@/types';

export const kbApi = {
  /** 一层目录（不递归）。path 为空字符串=根 */
  tree: (path = '') =>
    apiClient.get<FileNode[]>('/kb/tree', { params: { path } }).then(r => r.data),

  /** 单文件内容（text/html/json/md 直接返字符串；二进制 axios 走默认） */
  file: (path: string) =>
    apiClient.get<string>('/kb/file', {
      params: { path },
      transformResponse: [(d: string) => d],
    }).then(r => r.data),

  stats: () =>
    apiClient.get<{ exists: boolean; subdirs: number; files: number; bytes: number }>(
      '/kb/stats',
    ).then(r => r.data),
};
