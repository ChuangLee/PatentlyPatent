/**
 * 文件树 store：每项目一棵树。MVP 时只关心"当前项目的当前树"。
 * 持久化：sessionStorage（与 useProjectStore 同口径）
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { FileNode } from '@/types';
import { buildDefaultTree, listChildren, makeFile, makeFolder, descendantIds, pathOf, findById } from '@/utils/fileTree';

const KEY_PREFIX = 'pp.files.';

export const useFilesStore = defineStore('files', () => {
  const projectId = ref<string | null>(null);
  const tree = ref<FileNode[]>([]);
  const showHidden = ref(false);
  const currentFileId = ref<string | null>(null);

  function persist() {
    if (!projectId.value) return;
    sessionStorage.setItem(KEY_PREFIX + projectId.value, JSON.stringify(tree.value));
  }

  function load(pid: string): FileNode[] {
    const raw = sessionStorage.getItem(KEY_PREFIX + pid);
    if (!raw) return [];
    try { return JSON.parse(raw) as FileNode[]; }
    catch { return []; }
  }

  /** 切换项目；若已有缓存使用缓存，否则用传入的 initialTree（来自 fixture），否则建默认树 */
  function attach(pid: string, initialTree?: FileNode[]) {
    projectId.value = pid;
    const cached = load(pid);
    if (cached.length) {
      tree.value = cached;
    } else if (initialTree && initialTree.length) {
      tree.value = [...initialTree];
      persist();
    } else {
      tree.value = buildDefaultTree();
      persist();
    }
    currentFileId.value = null;
  }

  // --- queries ---
  const visibleRoots = computed(() =>
    listChildren(tree.value, null).filter(n => showHidden.value || !n.hidden),
  );

  function children(parentId: string | null): FileNode[] {
    return listChildren(tree.value, parentId).filter(n => showHidden.value || !n.hidden);
  }

  function getNode(id: string) { return findById(tree.value, id); }
  const currentNode = computed(() =>
    currentFileId.value ? findById(tree.value, currentFileId.value) ?? null : null,
  );

  function breadcrumb(id: string): string { return pathOf(tree.value, id); }

  // --- mutations ---
  function selectFile(id: string | null) { currentFileId.value = id; }

  function addFile(opts: Parameters<typeof makeFile>[0]): FileNode {
    const n = makeFile(opts);
    tree.value.push(n);
    persist();
    return n;
  }

  function addFolder(opts: Parameters<typeof makeFolder>[0]): FileNode {
    const n = makeFolder(opts);
    tree.value.push(n);
    persist();
    return n;
  }

  /** 直接 push 现成的 FileNode（agent 流式 spawn 用） */
  function pushNode(n: FileNode) {
    tree.value.push(n);
    persist();
  }

  function rename(id: string, newName: string) {
    const n = findById(tree.value, id);
    if (!n) return;
    n.name = newName;
    n.updatedAt = new Date().toISOString();
    persist();
  }

  function move(id: string, newParentId: string | null) {
    const n = findById(tree.value, id);
    if (!n) return;
    if (id === newParentId) return;
    if (descendantIds(tree.value, id).includes(newParentId ?? '__null__')) return;
    n.parentId = newParentId;
    n.updatedAt = new Date().toISOString();
    persist();
  }

  function remove(id: string) {
    const ids = new Set(descendantIds(tree.value, id));
    tree.value = tree.value.filter(n => !ids.has(n.id));
    if (currentFileId.value && ids.has(currentFileId.value)) currentFileId.value = null;
    persist();
  }

  function writeContent(id: string, content: string) {
    const n = findById(tree.value, id);
    if (!n || n.kind !== 'file') return;
    n.content = content;
    n.size = new Blob([content]).size;
    n.updatedAt = new Date().toISOString();
    persist();
  }

  function toggleHidden() { showHidden.value = !showHidden.value; }

  function reset() {
    projectId.value = null;
    tree.value = [];
    currentFileId.value = null;
  }

  return {
    projectId, tree, showHidden, currentFileId, currentNode,
    visibleRoots, children, getNode, breadcrumb,
    attach, selectFile, addFile, addFolder, pushNode,
    rename, move, remove, writeContent, toggleHidden, reset,
  };
});
