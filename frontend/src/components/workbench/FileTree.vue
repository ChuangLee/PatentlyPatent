<script setup lang="ts">
/**
 * 文件树组件 — Antd Vue a-tree + 自定义节点 slot
 * 数据源：useFilesStore（要求父组件先 attach）
 */
import { computed, ref, h, watch, nextTick } from 'vue';
import ATree from 'ant-design-vue/es/tree';
import AButton from 'ant-design-vue/es/button';
import AModal from 'ant-design-vue/es/modal';
import AInput from 'ant-design-vue/es/input';
import AUpload from 'ant-design-vue/es/upload';
import ADropdown from 'ant-design-vue/es/dropdown';
import AMenu, { Item as AMenuItem } from 'ant-design-vue/es/menu';
import ATooltip from 'ant-design-vue/es/tooltip';
import AProgress from 'ant-design-vue/es/progress';
import message from 'ant-design-vue/es/message';
import {
  FolderAddOutlined,
  UploadOutlined,
  DeleteOutlined,
  ReloadOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  ColumnHeightOutlined,
  ColumnWidthOutlined,
} from '@ant-design/icons-vue';
import { useFilesStore } from '@/stores/files';
import { filesApi } from '@/api/files';
import { kbApi } from '@/api/kb';
import type { FileNode, FileMime } from '@/types';

const props = defineProps<{ projectId: string }>();

const files = useFilesStore();
const wrapNames = ref(false);   // 多行 / 单行
const checkable = ref(false);   // 多选模式

// 选中节点（用于"在选中文件夹下创建/上传"）
const selectedKeys = ref<string[]>([]);
const expandedKeys = ref<string[]>([]);
const checkedKeys = ref<string[]>([]);   // 多选模式下的勾选 keys

function onCheck(keys: any) {
  // a-tree check 事件返 keys 数组（或对象，看 checkStrictly）
  checkedKeys.value = Array.isArray(keys) ? keys.map(String) : (keys.checked || []).map(String);
}

function toggleCheckable() {
  checkable.value = !checkable.value;
  if (!checkable.value) checkedKeys.value = [];
}

function batchDelete() {
  const ids = checkedKeys.value.filter(id => {
    const n = files.getNode(id);
    return n && n.parentId !== null;  // 不允许删根目录
  });
  if (ids.length === 0) {
    message.info('请先勾选要删除的文件 / 文件夹（根目录不可删）');
    return;
  }
  AModal.confirm({
    title: `确认批量删除 ${ids.length} 项？`,
    content: '将连同子项一并删除，无法恢复。',
    okText: '全部删除', okType: 'danger', cancelText: '取消',
    onOk() {
      const removed = files.removeMany(ids);
      checkedKeys.value = [];
      message.success(`已删除 ${removed} 项`);
    },
  });
}

/** 根节点默认全展开 */
function ensureRootsExpanded() {
  const rootIds = files.tree
    .filter((n: FileNode) => n.parentId === null)
    .map((n: FileNode) => n.id);
  for (const id of rootIds) {
    if (!expandedKeys.value.includes(id)) expandedKeys.value.push(id);
  }
}
ensureRootsExpanded();

/** 当前选中文件夹（决定新建/上传的目标目录）；若选中文件，取其父；默认 root-user */
const currentFolderId = computed<string | null>(() => {
  const sid = selectedKeys.value[0];
  if (!sid) {
    const rootUser = files.tree.find((n: FileNode) => n.id === 'root-user');
    return rootUser ? rootUser.id : (files.visibleRoots[0]?.id ?? null);
  }
  const node = files.getNode(sid);
  if (!node) return null;
  return node.kind === 'folder' ? node.id : node.parentId;
});

/** 把 FileNode[] 适配成 a-tree 需要的 tree-data */
type AntdTreeNode = {
  key: string;
  title: string;
  isLeaf: boolean;
  raw: FileNode;
  children?: AntdTreeNode[];
};

function toAntdTreeData(parentId: string | null): AntdTreeNode[] {
  return files.children(parentId).map((n: FileNode) => ({
    key: n.id,
    title: n.name,
    isLeaf: n.kind === 'file',
    raw: n,
    children: n.kind === 'folder' ? toAntdTreeData(n.id) : undefined,
  }));
}

// v0.22: 专利知识 kb 只读虚拟节点（懒加载子节点）
const kbVirtualRoot: FileNode = {
  id: 'kb-root',
  name: '专利知识',
  kind: 'folder',
  parentId: null,
  source: 'kb',
  hidden: false,
  createdAt: '',
  updatedAt: '',
};
const kbChildrenById = ref<Record<string, FileNode[]>>({});  // 缓存已加载层级
const kbLoadedKeys = ref<Set<string>>(new Set());

function kbToAntdNode(n: FileNode): AntdTreeNode {
  const cached = kbChildrenById.value[n.id];
  return {
    key: n.id,
    title: n.name,
    isLeaf: n.kind === 'file',
    raw: n,
    children: cached ? cached.map(kbToAntdNode) : undefined,
  };
}

async function loadKbChildren(node: AntdTreeNode): Promise<void> {
  if (kbLoadedKeys.value.has(node.key)) return;
  const path = (node.raw.kbPath ?? '');  // root 时为空
  try {
    const list = await kbApi.tree(path);
    kbChildrenById.value[node.key] = list;
    kbLoadedKeys.value.add(node.key);
  } catch (e: any) {
    message.error(`加载专利知识失败：${e?.message || e}`);
  }
}

/** a-tree loadData hook（仅 kb 节点用；非 kb 节点 children 已是同步） */
function onLoadData(node: any): Promise<void> {
  const raw = node?.raw as FileNode | undefined;
  if (raw?.source === 'kb' && raw.kind === 'folder') {
    return loadKbChildren(node as AntdTreeNode);
  }
  return Promise.resolve();
}

const treeData = computed<AntdTreeNode[]>(() => {
  const projectNodes = toAntdTreeData(null);
  return [...projectNodes, kbToAntdNode(kbVirtualRoot)];
});

/** 检查节点是否只读（kb 全部只读） */
function isReadonly(n: FileNode | undefined | null): boolean {
  return !!n && n.source === 'kb';
}

/** 工具：当前选中节点是否 kb（用于 disable 按钮） */
const selectedIsKb = computed<boolean>(() => {
  const id = selectedKeys.value[0];
  if (!id) return false;
  // 先看 store
  const n = files.getNode(id);
  if (n) return n.source === 'kb';
  // store 没有 → 看是否 kb 缓存里
  for (const arr of Object.values(kbChildrenById.value)) {
    const hit = arr.find(x => x.id === id);
    if (hit) return true;
  }
  return id.startsWith('kb');
});

/** 文件 icon by mime */
function iconFor(node: FileNode): string {
  if (node.kind === 'folder') {
    if (node.id === 'kb-root') return '📚';
    if (node.source === 'kb') return '📂';
    return '📁';
  }
  const m: FileMime | undefined = node.mime;
  if (m === 'text/markdown') return '📄';
  if (m === 'text/plain') return '📄';
  if (m === 'application/json') return '📄';
  if (m === 'application/pdf') return '📑';
  if (m === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') return '📝';
  if (m === 'text/x-link') return '🔗';
  if (m && m.startsWith('image/')) return '🖼';
  return '📦';
}

function childCount(node: FileNode): number {
  if (node.kind !== 'folder') return 0;
  return files.children(node.id).length;
}

// ─── 新建文件夹 ───
const newFolderOpen = ref(false);
const newFolderName = ref('');
function openNewFolder() {
  newFolderName.value = '';
  newFolderOpen.value = true;
}
function confirmNewFolder() {
  const name = newFolderName.value.trim();
  if (!name) {
    message.warning('请输入文件夹名');
    return;
  }
  if (currentFolderId.value === null) {
    message.error('请先在左侧选择一个父文件夹');
    return;
  }
  files.addFolder({ name, parentId: currentFolderId.value, source: 'user' });
  newFolderOpen.value = false;
  message.success('已创建文件夹');
}

// ─── 上传（伪上传，仅转 FileNode） ───
function inferMimeFromName(name: string): FileMime {
  const lower = name.toLowerCase();
  if (lower.endsWith('.md') || lower.endsWith('.markdown')) return 'text/markdown';
  if (lower.endsWith('.json')) return 'application/json';
  if (lower.endsWith('.pdf')) return 'application/pdf';
  if (lower.endsWith('.docx')) return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  if (lower.endsWith('.png')) return 'image/png';
  if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
  if (lower.endsWith('.svg')) return 'image/svg+xml';
  return 'text/plain';
}

async function readAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onerror = () => reject(r.error);
    r.onload = () => resolve(String(r.result ?? ''));
    r.readAsText(file);
  });
}

// 仅文本类先读取内容；二进制不读，仅记录元数据
async function beforeUpload(file: File): Promise<boolean> {
  if (currentFolderId.value === null) {
    message.error('请先选择一个父文件夹');
    return false;
  }
  const mime = inferMimeFromName(file.name);
  let content: string | undefined;
  if (mime === 'text/markdown' || mime === 'text/plain' || mime === 'application/json') {
    try { content = await readAsText(file); } catch { /* ignore */ }
  }
  files.addFile({
    name: file.name,
    parentId: currentFolderId.value,
    mime,
    content,
    size: file.size,
    source: 'user',
  });
  message.success(`已添加：${file.name}`);
  return false; // 阻止真实上传
}

// ─── 原生 HTML drag-and-drop 多文件批上传 ───
const nativeDropActive = ref(false);
const nativeDropCount = ref(0);
const nativeDropUploading = ref(false);
// v0.14-B: 批上传单文件进度
const uploadIndex = ref(0);   // 1-based 当前正在上传的序号
const uploadTotal = ref(0);
const uploadCurrentName = ref('');
const uploadPercent = computed(() =>
  uploadTotal.value > 0
    ? Math.round((uploadIndex.value / uploadTotal.value) * 100)
    : 0,
);

/** 解析批上传的目标父文件夹 id */
function resolveDropTargetFolderId(): { id: string | null; name: string } {
  // 当前选中 folder 优先
  if (currentFolderId.value) {
    const n = files.getNode(currentFolderId.value);
    if (n && n.kind === 'folder') {
      return { id: n.id, name: n.name };
    }
  }
  // 找 source==='user' && parentId===null 的根（"我的资料/"）
  const rootUser = files.tree.find(
    (n: FileNode) => n.parentId === null && n.source === 'user' && n.kind === 'folder',
  );
  if (rootUser) return { id: rootUser.id, name: rootUser.name };
  // 兜底：第一个根文件夹
  const anyRoot = files.tree.find((n: FileNode) => n.parentId === null && n.kind === 'folder');
  return anyRoot ? { id: anyRoot.id, name: anyRoot.name } : { id: null, name: '根目录' };
}

function isTextLikeMime(m: FileMime): boolean {
  return m === 'text/markdown' || m === 'text/plain' || m === 'application/json';
}

function onNativeDragOver(e: DragEvent) {
  // 只接 OS 文件拖入（dataTransfer.types 含 'Files'），不拦截内部节点拖拽
  const types = e.dataTransfer?.types;
  if (!types || !Array.from(types).includes('Files')) return;
  e.preventDefault();
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
  nativeDropActive.value = true;
  // dragover 不一定能拿到 files.length（多数浏览器为 0），用 items.length 作提示
  const itemsLen = e.dataTransfer?.items?.length ?? 0;
  if (itemsLen > 0) nativeDropCount.value = itemsLen;
}

function onNativeDragLeave(e: DragEvent) {
  // 离开容器外才清；relatedTarget 为 null 或不在容器内时
  const related = e.relatedTarget as Node | null;
  const current = e.currentTarget as HTMLElement | null;
  if (!current) return;
  if (!related || !current.contains(related)) {
    nativeDropActive.value = false;
    nativeDropCount.value = 0;
  }
}

async function onNativeDrop(e: DragEvent) {
  const types = e.dataTransfer?.types;
  if (!types || !Array.from(types).includes('Files')) return;
  e.preventDefault();
  nativeDropActive.value = false;
  nativeDropCount.value = 0;

  const fileList = e.dataTransfer?.files;
  if (!fileList || fileList.length === 0) return;
  const fileArr: File[] = Array.from(fileList);

  const { id: targetParentId, name: targetName } = resolveDropTargetFolderId();
  if (!targetParentId) {
    message.error('未找到上传目标文件夹');
    return;
  }

  nativeDropUploading.value = true;
  uploadTotal.value = fileArr.length;
  uploadIndex.value = 0;
  uploadCurrentName.value = '';
  let okCount = 0;
  const pid = props.projectId;

  // 顺序上传：FileReader + 后端调用串行，避免一次性把大文件全读进内存
  for (let i = 0; i < fileArr.length; i++) {
    const f = fileArr[i];
    uploadCurrentName.value = f.name;
    try {
      const mime = inferMimeFromName(f.name);
      let content: string | undefined;
      if (isTextLikeMime(mime)) {
        try { content = await readAsText(f); } catch { /* 二进制兜底：忽略 */ }
      }
      const body: Partial<FileNode> = {
        name: f.name,
        kind: 'file',
        parentId: targetParentId,
        source: 'user',
        mime,
        size: f.size,
        ...(content !== undefined ? { content } : {}),
      };
      const node = await filesApi.create(pid, body);
      files.pushNode(node);
      okCount += 1;
    } catch (err) {
      console.error('[FileTree native drop] upload failed', f.name, err);
      message.error(`上传失败：${f.name}`);
    }
    uploadIndex.value = i + 1;  // 完成第 i+1 个
  }

  nativeDropUploading.value = false;
  uploadCurrentName.value = '';
  uploadIndex.value = 0;
  uploadTotal.value = 0;
  if (okCount > 0) {
    message.success(`已上传 ${okCount} 个文件到 ${targetName}`);
  }
}

// ─── 节点选中 / 展开 ───
const kbPreviewOpen = ref(false);
const kbPreviewNode = ref<FileNode | null>(null);
const kbPreviewContent = ref('');
const kbPreviewHtml = ref('');   // v0.27: md 渲染后的 HTML
const kbPreviewLoading = ref(false);

/** v0.27: 把 md 内的相对图片路径转成 kb file 端点；保持绝对 URL 不变 */
function _resolveKbImgSrc(currentMdPath: string, src: string): string {
  if (/^https?:\/\//i.test(src) || src.startsWith('data:')) return src;
  // 相对路径：基于 md 所在目录
  const dir = currentMdPath.includes('/') ? currentMdPath.replace(/\/[^/]*$/, '') : '';
  const joined = dir ? `${dir}/${src.replace(/^\.?\//, '')}` : src.replace(/^\.?\//, '');
  return kbDownloadUrl(joined);
}

function _escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));
}

async function _renderMarkdown(md: string, mdPath: string): Promise<string> {
  const { marked } = await import('marked');
  const DOMPurify = (await import('dompurify')).default;
  const renderer = new marked.Renderer();
  renderer.image = (img: any) => {
    const href = _resolveKbImgSrc(mdPath, String(img.href || ''));
    const title = img.title ? ` title="${_escapeHtml(String(img.title))}"` : '';
    const alt = img.text ? _escapeHtml(String(img.text)) : '';
    return `<img src="${_escapeHtml(href)}" alt="${alt}"${title} loading="lazy" />`;
  };
  const html = await marked.parse(md, { renderer, breaks: true, gfm: true }) as string;
  return DOMPurify.sanitize(html, { ADD_ATTR: ['target', 'loading'] });
}

function findKbNode(id: string): FileNode | null {
  for (const arr of Object.values(kbChildrenById.value)) {
    const hit = arr.find(x => x.id === id);
    if (hit) return hit;
  }
  return id === 'kb-root' ? kbVirtualRoot : null;
}

async function openKbPreview(node: FileNode) {
  kbPreviewNode.value = node;
  kbPreviewOpen.value = true;
  kbPreviewContent.value = '';
  kbPreviewHtml.value = '';
  if (node.kind !== 'file' || !node.kbPath) return;
  const m = node.mime || '';
  // 二进制类不预加载，让 iframe 走 url
  if (m.startsWith('application/pdf') || m.startsWith('image/')) return;
  kbPreviewLoading.value = true;
  try {
    const text = await kbApi.file(node.kbPath);
    kbPreviewContent.value = text;
    if (m === 'text/markdown') {
      kbPreviewHtml.value = await _renderMarkdown(text, node.kbPath);
    } else if (m === 'text/html') {
      // 已是 html，让 sanitize 兜底
      const DOMPurify = (await import('dompurify')).default;
      kbPreviewHtml.value = DOMPurify.sanitize(text, { ADD_ATTR: ['target'] });
    }
  } catch (e: any) {
    kbPreviewContent.value = `（加载失败：${e?.message || e}）`;
  } finally {
    kbPreviewLoading.value = false;
  }
}

function kbDownloadUrl(path: string): string {
  return `/patent/api/kb/file?path=${encodeURIComponent(path)}`;
}

function onSelect(keys: (string | number)[]) {
  selectedKeys.value = keys.map(k => String(k));
  const id = selectedKeys.value[0];
  if (!id) return;
  // kb 节点走 modal 预览（不入 store，不持久化）
  const kbNode = findKbNode(id);
  if (kbNode) {
    if (kbNode.kind === 'file') openKbPreview(kbNode);
    return;
  }
  const node = files.getNode(id);
  if (!node) return;
  files.selectFile(id);
}

function onExpand(keys: (string | number)[]) {
  expandedKeys.value = keys.map(k => String(k));
}

// ─── 拖拽 ───
type DropInfo = {
  node: { key: string | number };
  dragNode: { key: string | number };
  dropToGap: boolean;
  dropPosition: number;
};

// v0.11-D + v0.12-D: 拖拽过程目标 key 持续高亮
// 用 dragover 而非 dragenter（dragenter 切到子节点会丢失父高亮；dragover 每 ~50ms 触发一次更稳）
const dragOverKey = ref<string | null>(null);

function setDragTarget(key: string | number | null | undefined) {
  if (!key) {
    dragOverKey.value = null;
    return;
  }
  const k = String(key);
  const node = files.getNode(k);
  // 只高亮 folder 节点
  if (node?.kind === 'folder' && dragOverKey.value !== k) {
    dragOverKey.value = k;
  } else if (!node || node.kind !== 'folder') {
    dragOverKey.value = null;
  }
}

function onDragEnter(info: { node: { key: string | number } }) {
  setDragTarget(info.node.key);
}

function onDragOver(info: { node: { key: string | number } }) {
  setDragTarget(info.node.key);
}

function onDragLeave() {
  // 不在此清掉（dragover 仍会立刻覆盖正确目标）
}

function onDragEnd() {
  dragOverKey.value = null;
}

function onDrop(info: DropInfo) {
  dragOverKey.value = null;
  const dragId = String(info.dragNode.key);
  const targetId = String(info.node.key);
  // kb 节点拒绝任何拖拽（拖入或拖出）
  if (findKbNode(dragId) || findKbNode(targetId)) {
    message.info('「专利知识」是只读的，不可拖拽');
    return;
  }
  const target = files.getNode(targetId);
  if (!target) return;

  let newParentId: string | null;
  if (target.kind === 'folder' && !info.dropToGap) {
    // 拖到文件夹内部
    newParentId = target.id;
  } else {
    // 拖到旁边 → 取目标的父
    newParentId = target.parentId;
  }
  files.move(dragId, newParentId);
}

// ─── 右键菜单 ───
const contextNodeId = ref<string | null>(null);

function copyPath(id: string) {
  const path = files.breadcrumb(id);
  if (navigator.clipboard) {
    navigator.clipboard.writeText(path).then(
      () => message.success('已复制路径'),
      () => message.error('复制失败'),
    );
  } else {
    message.info(path);
  }
}

const renameOpen = ref(false);
const renameValue = ref('');
const renameTargetId = ref<string | null>(null);

function openRename(id: string) {
  const n = files.getNode(id);
  if (!n) return;
  renameTargetId.value = id;
  renameValue.value = n.name;
  renameOpen.value = true;
}
function confirmRename() {
  const id = renameTargetId.value;
  const name = renameValue.value.trim();
  if (!id || !name) {
    renameOpen.value = false;
    return;
  }
  files.rename(id, name);
  renameOpen.value = false;
  message.success('已重命名');
}

function confirmRemove(id: string) {
  const n = files.getNode(id);
  if (!n) return;
  AModal.confirm({
    title: `确认删除 "${n.name}"？`,
    content: n.kind === 'folder' ? '将连同子项一并删除，无法恢复。' : '删除后无法恢复。',
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk() {
      files.remove(id);
      message.success('已删除');
    },
  });
}

// 工具栏：删除当前选中
function deleteSelected() {
  const id = selectedKeys.value[0];
  if (!id) {
    message.info('请先点选一个文件或文件夹');
    return;
  }
  if (findKbNode(id)) {
    message.warning('「专利知识」是只读的，不可删除');
    return;
  }
  const node = files.getNode(id);
  if (!node) return;
  // 不允许删除根目录
  if (node.parentId === null) {
    message.warning('不能删除根目录');
    return;
  }
  confirmRemove(id);
}

// 工具栏：刷新（重置缓存重新装载）
function refreshTree() {
  const pid = files.projectId;
  if (!pid) return;
  // 清 sessionStorage，重 attach
  sessionStorage.removeItem('pp.files.' + pid);
  // 触发重新装载需要 initialTree——这里我们重新用现 tree 备份再 attach 等价
  const backup = JSON.parse(JSON.stringify(files.tree));
  files.attach(pid, backup);
  message.success('已刷新');
}

function toggleWrap() { wrapNames.value = !wrapNames.value; }

// ─── v0.21 任务 4: 滚动到 agent spawn 的新节点 ───────────────────────────────
const treeContainerRef = ref<HTMLElement | null>(null);

/**
 * 滚动到指定 id 的树节点。
 * antd-vue 的 a-tree 节点 DOM 没有标准的 data-node-key，但 .ant-tree-treenode 节点可通过
 * 内部唯一的 .ant-tree-node-content-wrapper / span 文本定位；这里采取保险策略：
 *   1) 先确保该节点的所有祖先 expanded（否则 DOM 不存在）
 *   2) 用 querySelector 在容器内找带 [data-pp-node-id="<id>"] 属性的渲染元素（renderNodeTitle 写入）
 *   3) 找到则 scrollIntoView({behavior:'smooth', block:'center'}) + 短暂高亮
 */
async function scrollToNode(id: string) {
  // 1) 展开所有祖先
  const node = files.getNode(id);
  if (!node) return;
  const ancestors: string[] = [];
  let cur: FileNode | undefined = node;
  while (cur && cur.parentId) {
    ancestors.push(cur.parentId);
    cur = files.getNode(cur.parentId);
  }
  let expandedChanged = false;
  for (const aid of ancestors) {
    if (!expandedKeys.value.includes(aid)) {
      expandedKeys.value.push(aid);
      expandedChanged = true;
    }
  }
  // 等 a-tree 重渲染
  if (expandedChanged) await nextTick();
  await nextTick();

  // 2) 查 DOM
  const container = treeContainerRef.value;
  if (!container) return;
  const el = container.querySelector<HTMLElement>(`[data-pp-node-id="${CSS.escape(id)}"]`);
  if (!el) return;
  // 3) 滚动 + 闪烁高亮
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  el.classList.add('pp-spawn-flash');
  setTimeout(() => el.classList.remove('pp-spawn-flash'), 1600);
}

// watch store 里的 lastSpawnedNodeId — agent 写入 → FileTree 自动滚
watch(() => files.lastSpawnedNodeId, (id) => {
  if (!id) return;
  scrollToNode(id);
});

defineExpose({ scrollToNode });

// 节点 title 渲染（slot）
function renderNodeTitle(node: AntdTreeNode) {
  const raw = node.raw;
  const icon = iconFor(raw);
  const cnt = raw.kind === 'folder' ? childCount(raw) : 0;
  const isDragTarget = dragOverKey.value === raw.id && raw.kind === 'folder';
  return h(
    'span',
    {
      class: ['pp-tree-node', isDragTarget ? 'pp-drag-over' : ''].filter(Boolean).join(' '),
      // v0.21 任务 4: 暴露节点 id 给 scrollToNode 查找
      'data-pp-node-id': raw.id,
      onContextmenu: (e: MouseEvent) => {
        e.preventDefault();
        contextNodeId.value = raw.id;
      },
      style: {
        display: 'inline-flex', alignItems: 'center', gap: '6px',
        opacity: raw.hidden ? 0.55 : 1,
      },
    },
    [
      h('span', { style: { fontSize: '14px' } }, icon),
      h('span', { style: { fontSize: '13px' } }, raw.name),
      raw.kind === 'folder' && cnt > 0
        ? h('span', { style: { fontSize: '11px', color: '#aaa' } }, `(${cnt})`)
        : null,
    ],
  );
}
</script>

<template>
  <div style="display:flex;flex-direction:column;height:100%;overflow:hidden">
    <!-- 工具栏（图标 + tooltip） -->
    <div class="pp-toolbar">
      <ATooltip :title="`新建文件夹（在 ${currentFolderId ? files.breadcrumb(currentFolderId) : '根目录'} 下）`">
        <AButton type="text" size="small" @click="openNewFolder">
          <template #icon><FolderAddOutlined /></template>
        </AButton>
      </ATooltip>
      <AUpload :before-upload="beforeUpload" :show-upload-list="false" multiple>
        <ATooltip title="上传文件（多选支持，文件存当前选中文件夹内）">
          <AButton type="text" size="small">
            <template #icon><UploadOutlined /></template>
          </AButton>
        </ATooltip>
      </AUpload>
      <ATooltip title="删除当前选中">
        <AButton type="text" size="small" :danger="!!selectedKeys[0]" @click="deleteSelected">
          <template #icon><DeleteOutlined /></template>
        </AButton>
      </ATooltip>
      <ATooltip :title="checkable ? `批量删（已勾选 ${checkedKeys.length} 项）` : '开启多选模式（每节点出 checkbox，可批量删）'">
        <AButton type="text" size="small"
                 :class="{ 'pp-active': checkable }"
                 @click="checkable && checkedKeys.length ? batchDelete() : toggleCheckable()">
          <template #icon>
            <span style="font-size:12px">{{ checkable ? `🗑×${checkedKeys.length}` : '☐' }}</span>
          </template>
        </AButton>
      </ATooltip>
      <ATooltip title="刷新（从缓存重载）">
        <AButton type="text" size="small" @click="refreshTree">
          <template #icon><ReloadOutlined /></template>
        </AButton>
      </ATooltip>
      <span style="flex:1"></span>
      <ATooltip :title="wrapNames ? '切到单行显示' : '切到多行显示（长名换行）'">
        <AButton type="text" size="small" @click="toggleWrap">
          <template #icon>
            <ColumnHeightOutlined v-if="wrapNames" />
            <ColumnWidthOutlined v-else />
          </template>
        </AButton>
      </ATooltip>
      <ATooltip :title="files.showHidden ? '隐藏 .ai-internal 等隐藏项' : '显示 .ai-internal 等隐藏项'">
        <AButton type="text" size="small" @click="files.toggleHidden">
          <template #icon>
            <EyeOutlined v-if="files.showHidden" />
            <EyeInvisibleOutlined v-else />
          </template>
        </AButton>
      </ATooltip>
    </div>

    <!-- 树（含原生 HTML drop zone：从 OS 拖文件到此区域批上传） -->
    <div
      ref="treeContainerRef"
      class="pp-tree-dropzone"
      :class="{ 'pp-tree-drop-active': nativeDropActive }"
      style="flex:1;overflow:auto;padding:6px;position:relative"
      @dragover="onNativeDragOver"
      @dragleave="onNativeDragLeave"
      @drop="onNativeDrop"
    >
      <!-- 拖拽叠层提示 -->
      <div v-if="nativeDropActive && !nativeDropUploading" class="pp-tree-drop-overlay">
        <div class="pp-tree-drop-hint">
          释放以上传 {{ nativeDropCount > 0 ? nativeDropCount : '' }} 个文件
        </div>
      </div>
      <!-- v0.14-B: 上传进度叠层 -->
      <div v-if="nativeDropUploading" class="pp-tree-upload-overlay">
        <div class="pp-tree-upload-card">
          <div class="pp-tree-upload-title">
            上传中 {{ uploadIndex }} / {{ uploadTotal }}
          </div>
          <div class="pp-tree-upload-name" :title="uploadCurrentName">
            {{ uploadCurrentName || '准备中…' }}
          </div>
          <AProgress :percent="uploadPercent" size="small" status="active" />
        </div>
      </div>
      <ADropdown :trigger="['contextmenu']">
        <div>
          <ATree
            :tree-data="treeData"
            :selected-keys="selectedKeys"
            :expanded-keys="expandedKeys"
            :checkable="checkable"
            :checked-keys="checkedKeys"
            :load-data="onLoadData"
            :class="{ 'pp-tree-wrap': wrapNames, 'pp-tree-dragging': dragOverKey !== null }"
            block-node
            draggable
            @select="onSelect"
            @expand="onExpand"
            @check="onCheck"
            @drop="onDrop"
            @dragenter="onDragEnter"
            @dragover="onDragOver"
            @dragleave="onDragLeave"
            @dragend="onDragEnd"
          >
            <template #title="node">
              <component :is="renderNodeTitle(node as AntdTreeNode)" />
            </template>
          </ATree>
        </div>
        <template #overlay>
          <AMenu v-if="contextNodeId">
            <AMenuItem key="rename" @click="openRename(contextNodeId!)">重命名</AMenuItem>
            <AMenuItem key="copy" @click="copyPath(contextNodeId!)">复制路径</AMenuItem>
            <AMenuItem key="remove" danger @click="confirmRemove(contextNodeId!)">删除</AMenuItem>
          </AMenu>
        </template>
      </ADropdown>

      <div v-if="treeData.length === 0" style="color:#aaa;font-size:12px;text-align:center;padding:24px">
        （空）
      </div>
    </div>

    <!-- 新建文件夹 modal -->
    <AModal v-model:open="newFolderOpen" title="新建文件夹" @ok="confirmNewFolder" ok-text="创建" cancel-text="取消">
      <AInput v-model:value="newFolderName" placeholder="文件夹名称" @press-enter="confirmNewFolder" />
      <p style="color:#888;font-size:12px;margin-top:8px">
        将创建在：<code>{{ currentFolderId ? files.breadcrumb(currentFolderId) : '（请先选择一个文件夹）' }}</code>
      </p>
    </AModal>

    <!-- 重命名 modal -->
    <AModal v-model:open="renameOpen" title="重命名" @ok="confirmRename" ok-text="保存" cancel-text="取消">
      <AInput v-model:value="renameValue" @press-enter="confirmRename" />
    </AModal>

    <!-- v0.22: 专利知识 kb 文件预览 modal（只读） -->
    <AModal
      v-model:open="kbPreviewOpen"
      :title="kbPreviewNode ? `📚 ${kbPreviewNode.name}（只读）` : '专利知识'"
      :footer="null"
      width="80vw"
      wrap-class-name="pp-kb-modal"
      :body-style="{ maxHeight: '78vh', overflow: 'auto', padding: '16px 20px' }"
    >
      <div v-if="kbPreviewLoading" style="text-align:center;padding:40px;color:#999">加载中…</div>
      <template v-else-if="kbPreviewNode?.kbPath">
        <!-- pdf -->
        <iframe
          v-if="(kbPreviewNode.mime || '').includes('pdf')"
          :src="kbDownloadUrl(kbPreviewNode.kbPath)"
          style="width:100%;height:70vh;border:0"
        />
        <!-- 图片 -->
        <img
          v-else-if="(kbPreviewNode.mime || '').startsWith('image/')"
          :src="kbDownloadUrl(kbPreviewNode.kbPath)"
          style="max-width:100%;height:auto"
        />
        <!-- v0.27: markdown / html 用 marked + DOMPurify 渲染 -->
        <div
          v-else-if="kbPreviewHtml && ((kbPreviewNode.mime || '') === 'text/markdown' || (kbPreviewNode.mime || '') === 'text/html')"
          class="pp-kb-md"
          v-html="kbPreviewHtml"
        />
        <!-- 其他文本/json：纯文本展示 -->
        <pre
          v-else
          style="white-space:pre-wrap;word-break:break-word;font-family:inherit;font-size:13px;line-height:1.65;margin:0"
        >{{ kbPreviewContent }}</pre>
      </template>
      <div style="margin-top:12px;padding-top:8px;border-top:1px solid #eee;color:#999;font-size:12px">
        来源：本项目 refs/专利专家知识库 ·
        <a v-if="kbPreviewNode?.kbPath" :href="kbDownloadUrl(kbPreviewNode.kbPath)" target="_blank">原文件直链</a>
      </div>
    </AModal>
  </div>
</template>

<style scoped>
.pp-tree-node {
  user-select: none;
  font-size: var(--pp-font-size-sm);
}
.pp-toolbar {
  display: flex;
  align-items: center;
  gap: var(--pp-space-1);
  padding: var(--pp-space-2) var(--pp-space-3);
  border-bottom: 1px solid var(--pp-color-border-soft);
  background: var(--pp-color-bg);
}
.pp-toolbar :deep(.ant-btn-text) {
  border-radius: var(--pp-radius-sm);
  transition: var(--pp-transition-fast);
}
.pp-toolbar :deep(.ant-btn-text:hover) {
  background: var(--pp-color-primary-soft) !important;
  color: var(--pp-color-primary) !important;
}
.pp-active {
  background: var(--pp-color-primary-soft) !important;
  color: var(--pp-color-primary) !important;
}
/* 选中节点高亮（primary-soft + 左侧 3px 竖线） */
:deep(.ant-tree .ant-tree-treenode-selected .ant-tree-node-content-wrapper),
:deep(.ant-tree .ant-tree-node-content-wrapper.ant-tree-node-selected) {
  background: var(--pp-color-primary-soft) !important;
  box-shadow: inset 3px 0 0 0 var(--pp-color-primary);
  border-radius: var(--pp-radius-sm);
}
:deep(.ant-tree .ant-tree-node-content-wrapper) {
  font-size: var(--pp-font-size-sm);
  padding: 2px var(--pp-space-2);
  border-radius: var(--pp-radius-sm);
  transition: var(--pp-transition-fast);
}
:deep(.ant-tree .ant-tree-node-content-wrapper:hover) {
  background: var(--pp-color-surface-hover) !important;
}
/* 拖拽过程：当前文件夹高亮 → 改为 primary-soft 蓝色 */
.pp-drag-over {
  background: var(--pp-color-primary-soft) !important;
  border: 2px dashed var(--pp-color-primary) !important;
  border-radius: var(--pp-radius-sm);
  padding: 0 var(--pp-space-1);
}
.pp-tree-dragging {
  /* 拖拽进行中给整个 tree 一点提示 */
  cursor: grabbing;
}
/* 原生拖拽（OS 文件 → 树容器）批上传视觉反馈 */
.pp-tree-dropzone {
  border: 2px dashed transparent;
  border-radius: var(--pp-radius-md);
  transition: border-color var(--pp-transition-fast), background-color var(--pp-transition-fast);
}
.pp-tree-drop-active {
  border-color: var(--pp-color-primary);
  background-color: var(--pp-color-primary-soft);
}
.pp-tree-drop-overlay {
  position: absolute;
  inset: 6px;
  pointer-events: none;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(91, 108, 255, 0.10);
  border-radius: var(--pp-radius-md);
  z-index: 5;
}
.pp-tree-drop-hint {
  background: var(--pp-color-primary);
  color: var(--pp-color-text-inverse);
  font-size: var(--pp-font-size-sm);
  font-weight: var(--pp-font-weight-medium);
  padding: var(--pp-space-2) var(--pp-space-4);
  border-radius: var(--pp-radius-full);
  box-shadow: var(--pp-shadow-md);
}
/* v0.14-B: 上传进度叠层 */
.pp-tree-upload-overlay {
  position: absolute;
  inset: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.85);
  border-radius: var(--pp-radius-md);
  z-index: 6;
  pointer-events: all;
}
.pp-tree-upload-card {
  background: var(--pp-color-surface);
  border: 1px solid var(--pp-color-border-soft);
  border-radius: var(--pp-radius-md);
  padding: var(--pp-space-4);
  width: min(85%, 280px);
  box-shadow: var(--pp-shadow-lg);
}
.pp-tree-upload-title {
  font-size: var(--pp-font-size-xs);
  color: var(--pp-color-text-secondary);
  font-weight: var(--pp-font-weight-semibold);
  margin-bottom: var(--pp-space-1);
}
.pp-tree-upload-name {
  font-size: var(--pp-font-size-sm);
  color: var(--pp-color-text);
  margin-bottom: var(--pp-space-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* v0.21 任务 4: agent spawn 节点闪烁高亮 */
.pp-spawn-flash {
  animation: pp-spawn-flash-anim 1.6s ease-out;
  border-radius: var(--pp-radius-sm);
}
@keyframes pp-spawn-flash-anim {
  0%   { background: rgba(91, 108, 255, 0.45); box-shadow: 0 0 0 4px rgba(91, 108, 255, 0.35); }
  60%  { background: rgba(91, 108, 255, 0.18); box-shadow: 0 0 0 2px rgba(91, 108, 255, 0.18); }
  100% { background: transparent; box-shadow: none; }
}
/* 多行显示：节点 title 换行 */
:deep(.pp-tree-wrap .ant-tree-node-content-wrapper) {
  white-space: normal !important;
  word-break: break-all;
  height: auto !important;
  min-height: 24px;
}
:deep(.pp-tree-wrap .pp-tree-node) {
  white-space: normal;
  word-break: break-all;
}
</style>

<!-- v0.22 kb modal 全局样式（modal 渲染在 body 下，需脱 scoped） -->
<style>
.pp-kb-modal .ant-modal-content {
  border-radius: var(--pp-radius-lg);
  overflow: hidden;
  box-shadow: var(--pp-shadow-xl);
}
.pp-kb-modal .ant-modal-header {
  background: var(--pp-color-primary);
  border-bottom: 0;
  padding: var(--pp-space-3) var(--pp-space-5);
}
.pp-kb-modal .ant-modal-title {
  color: var(--pp-color-text-inverse) !important;
  font-weight: var(--pp-font-weight-semibold);
}
/* v0.27 fix: 让 close 叉号完整显示在圆角内，避免被 overflow:hidden 切一半 */
.pp-kb-modal .ant-modal-close {
  top: 8px !important;
  right: 8px !important;
  width: 32px !important;
  height: 32px !important;
  border-radius: var(--pp-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  z-index: 10;
}
.pp-kb-modal .ant-modal-close-x {
  font-size: 16px;
  line-height: 1;
}
.pp-kb-modal .ant-modal-close:hover {
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
}

/* v0.27: markdown 渲染样式 */
.pp-kb-md {
  font-size: 14px;
  line-height: 1.75;
  color: var(--pp-color-text);
}
.pp-kb-md h1, .pp-kb-md h2, .pp-kb-md h3, .pp-kb-md h4 {
  margin: 1.4em 0 0.6em;
  font-weight: 600;
  color: var(--pp-color-text);
}
.pp-kb-md h1 { font-size: 22px; }
.pp-kb-md h2 { font-size: 18px; border-bottom: 1px solid var(--pp-color-border-soft); padding-bottom: 6px; }
.pp-kb-md h3 { font-size: 16px; }
.pp-kb-md p { margin: 0.7em 0; }
.pp-kb-md a { color: var(--pp-color-primary); text-decoration: none; }
.pp-kb-md a:hover { text-decoration: underline; }
.pp-kb-md img {
  max-width: 100%;
  height: auto;
  border-radius: var(--pp-radius-sm);
  border: 1px solid var(--pp-color-border-soft);
  margin: 0.6em 0;
  background: var(--pp-color-bg);
}
.pp-kb-md code {
  background: var(--pp-color-bg);
  padding: 2px 6px;
  border-radius: var(--pp-radius-sm);
  font-family: var(--pp-font-mono);
  font-size: 12.5px;
}
.pp-kb-md pre {
  background: var(--pp-color-bg);
  padding: 12px 14px;
  border-radius: var(--pp-radius-md);
  overflow-x: auto;
  border: 1px solid var(--pp-color-border-soft);
}
.pp-kb-md pre code { background: transparent; padding: 0; }
.pp-kb-md blockquote {
  margin: 0.8em 0;
  padding: 4px 14px;
  border-left: 3px solid var(--pp-color-primary);
  background: var(--pp-color-primary-soft);
  color: var(--pp-color-text-secondary);
  border-radius: 0 var(--pp-radius-sm) var(--pp-radius-sm) 0;
}
.pp-kb-md ul, .pp-kb-md ol { padding-left: 1.6em; }
.pp-kb-md li { margin: 0.3em 0; }
.pp-kb-md table {
  border-collapse: collapse;
  margin: 0.8em 0;
  width: 100%;
}
.pp-kb-md th, .pp-kb-md td {
  border: 1px solid var(--pp-color-border-soft);
  padding: 6px 10px;
  text-align: left;
}
.pp-kb-md th { background: var(--pp-color-bg); font-weight: 600; }
.pp-kb-md hr {
  border: none;
  border-top: 1px solid var(--pp-color-border-soft);
  margin: 1.6em 0;
}
</style>
