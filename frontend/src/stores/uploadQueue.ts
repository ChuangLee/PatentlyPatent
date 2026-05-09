/**
 * v0.35.4: 跨路由上传队列
 *
 * 报门时拖入的二进制 File 不能 sessionStorage（无法序列化），
 * 用 module-level Map 临时寄存：NewProjectModal enqueue → ProjectWorkbench take。
 *
 * 队列在浏览器 reload 时丢失（无所谓，那种场景用户在 dashboard 就能重传）。
 */

const _queue = new Map<string, File[]>();

export function enqueueUploads(projectId: string, files: File[]): void {
  if (!files.length) return;
  _queue.set(projectId, files);
}

export function takePendingUploads(projectId: string): File[] {
  const files = _queue.get(projectId) ?? [];
  _queue.delete(projectId);
  return files;
}

export function hasPendingUploads(projectId: string): boolean {
  return (_queue.get(projectId)?.length ?? 0) > 0;
}
