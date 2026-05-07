<script setup lang="ts">
/**
 * 文件树组件 — Antd Vue a-tree + 自定义节点 slot
 * 数据源：useFilesStore（要求父组件先 attach）
 */
import { computed, ref, h } from 'vue';
import {
  Tree as ATree,
  Button as AButton,
  Modal as AModal,
  Input as AInput,
  Upload as AUpload,
  Dropdown as ADropdown,
  Menu as AMenu,
  MenuItem as AMenuItem,
  Tooltip as ATooltip,
  Progress as AProgress,
  message,
} from 'ant-design-vue';
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

const treeData = computed<AntdTreeNode[]>(() => toAntdTreeData(null));

/** 文件 icon by mime */
function iconFor(node: FileNode): string {
  if (node.kind === 'folder') return '📁';
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
function onSelect(keys: (string | number)[]) {
  selectedKeys.value = keys.map(k => String(k));
  const id = selectedKeys.value[0];
  if (!id) return;
  const node = files.getNode(id);
  if (!node) return;
  if (node.kind === 'file') {
    files.selectFile(id);
  } else {
    // 文件夹：清空当前预览（让 previewer 显示子项列表）
    files.selectFile(id);
  }
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
  </div>
</template>

<style scoped>
.pp-tree-node {
  user-select: none;
}
.pp-toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px 6px;
  border-bottom: 1px solid #eee;
}
.pp-active {
  background: #e6f0ff !important;
  color: #1677ff !important;
}
/* 拖拽过程：当前文件夹高亮 */
.pp-drag-over {
  background: #fff7e6 !important;
  border: 2px dashed #faad14 !important;
  border-radius: 4px;
  padding: 0 4px;
}
.pp-tree-dragging {
  /* 拖拽进行中给整个 tree 一点提示 */
  cursor: grabbing;
}
/* 原生拖拽（OS 文件 → 树容器）批上传视觉反馈 */
.pp-tree-dropzone {
  border: 2px dashed transparent;
  border-radius: 6px;
  transition: border-color 0.15s, background-color 0.15s;
}
.pp-tree-drop-active {
  border-color: #1677ff;
  background-color: #e6f4ff;
}
.pp-tree-drop-overlay {
  position: absolute;
  inset: 6px;
  pointer-events: none;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(230, 244, 255, 0.55);
  border-radius: 4px;
  z-index: 5;
}
.pp-tree-drop-hint {
  background: #1677ff;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  padding: 6px 14px;
  border-radius: 16px;
  box-shadow: 0 2px 8px rgba(22, 119, 255, 0.35);
}
/* v0.14-B: 上传进度叠层 */
.pp-tree-upload-overlay {
  position: absolute;
  inset: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 4px;
  z-index: 6;
  pointer-events: all;
}
.pp-tree-upload-card {
  background: #fff;
  border: 1px solid #e6e6e6;
  border-radius: 8px;
  padding: 14px 16px;
  width: min(85%, 280px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}
.pp-tree-upload-title {
  font-size: 12px;
  color: #666;
  font-weight: 600;
  margin-bottom: 4px;
}
.pp-tree-upload-name {
  font-size: 13px;
  color: #1f1f1f;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
