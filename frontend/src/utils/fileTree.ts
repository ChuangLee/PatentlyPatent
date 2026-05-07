/**
 * 文件树工具：构造默认结构、增删改查、序列化辅助。
 * mid-fi 阶段全部在前端 in-memory，无后端持久化（除 sessionStorage 由 store 管理）。
 */
import type { FileNode } from '@/types';

let counter = 0;
function nid(prefix = 'fn'): string {
  counter += 1;
  return `${prefix}-${Date.now().toString(36)}-${counter.toString(36)}`;
}

const now = () => new Date().toISOString();

/** 项目初始默认 3 根目录：我的资料 / AI 输出 / .ai-internal（隐藏） */
export function buildDefaultTree(): FileNode[] {
  const t = now();
  return [
    { id: 'root-user',    name: '我的资料',     kind: 'folder', parentId: null, source: 'user',   createdAt: t, updatedAt: t },
    { id: 'root-ai',      name: 'AI 输出',      kind: 'folder', parentId: null, source: 'ai',     createdAt: t, updatedAt: t },
    { id: 'root-internal',name: '.ai-internal', kind: 'folder', parentId: null, source: 'system', hidden: true, createdAt: t, updatedAt: t },
  ];
}

export function findById(tree: FileNode[], id: string): FileNode | undefined {
  return tree.find(n => n.id === id);
}

/** 给定 parentId，返回直接子节点（按文件夹优先 + 名字字母排序） */
export function listChildren(tree: FileNode[], parentId: string | null): FileNode[] {
  return tree
    .filter(n => n.parentId === parentId)
    .sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === 'folder' ? -1 : 1;
      return a.name.localeCompare(b.name, 'zh-CN');
    });
}

/** 创建新节点（不入树，由调用方加进 store） */
export function makeFile(opts: {
  name: string; parentId: string | null;
  mime?: FileNode['mime']; content?: string; url?: string; size?: number;
  source?: FileNode['source'];
}): FileNode {
  const t = now();
  return {
    id: nid('f'),
    name: opts.name,
    kind: 'file',
    parentId: opts.parentId,
    source: opts.source ?? 'user',
    mime: opts.mime,
    content: opts.content,
    url: opts.url,
    size: opts.size ?? (opts.content ? new Blob([opts.content]).size : undefined),
    createdAt: t,
    updatedAt: t,
  };
}

export function makeFolder(opts: {
  name: string; parentId: string | null;
  source?: FileNode['source']; hidden?: boolean;
}): FileNode {
  const t = now();
  return {
    id: nid('d'),
    name: opts.name,
    kind: 'folder',
    parentId: opts.parentId,
    source: opts.source ?? 'user',
    hidden: opts.hidden,
    createdAt: t,
    updatedAt: t,
  };
}

/** 递归子节点 id 列表（含自身） */
export function descendantIds(tree: FileNode[], rootId: string): string[] {
  const out = [rootId];
  const stack = [rootId];
  while (stack.length) {
    const cur = stack.pop()!;
    for (const n of tree) {
      if (n.parentId === cur) {
        out.push(n.id);
        stack.push(n.id);
      }
    }
  }
  return out;
}

/** 路径字符串（"/我的资料/foo/bar"），用于 breadcrumb */
export function pathOf(tree: FileNode[], id: string): string {
  const node = findById(tree, id);
  if (!node) return '';
  const parts: string[] = [node.name];
  let cur = node.parentId;
  while (cur) {
    const p = findById(tree, cur);
    if (!p) break;
    parts.unshift(p.name);
    cur = p.parentId;
  }
  return '/' + parts.join('/');
}

/** 把 Attachment[] 转换成"我的资料/"下的 FileNode[]（迁移老数据用） */
export function attachmentsToFileNodes(
  attachments: { type: 'file'|'link'|'note'; name: string; size?: number; mime?: string;
                 url?: string; content?: string; addedAt: string }[],
  parentId: string,
): FileNode[] {
  return attachments.map(a => {
    if (a.type === 'link') {
      return makeFile({
        name: a.name, parentId,
        mime: 'text/x-link', url: a.url, source: 'user',
      });
    }
    if (a.type === 'note') {
      return makeFile({
        name: a.name + '.md', parentId,
        mime: 'text/markdown', content: a.content, source: 'user',
      });
    }
    // file
    return makeFile({
      name: a.name, parentId,
      mime: (a.mime as FileNode['mime']) ?? 'text/plain',
      size: a.size, source: 'user',
    });
  });
}
