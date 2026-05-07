<script setup lang="ts">
/**
 * 文件预览器 — 根据 useFilesStore().currentNode 渲染不同 mime 类型
 */
import { computed, ref, watch } from 'vue';
import {
  Button as AButton,
  Empty as AEmpty,
  Spin as ASpin,
  Textarea as ATextarea,
  message,
} from 'ant-design-vue';
import { marked } from 'marked';
import { useFilesStore } from '@/stores/files';
import { apiClient } from '@/api/client';
import type { FileNode } from '@/types';

const DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

const files = useFilesStore();

const node = computed<FileNode | null>(() => files.currentNode);

// docx 预览状态
const docxHtml = ref<string>('');
const docxLoading = ref(false);
const docxError = ref<string>('');

async function loadDocxPreview(n: FileNode) {
  docxHtml.value = '';
  docxError.value = '';
  if (!n.url) {
    docxError.value = '未提供下载地址';
    return;
  }
  docxLoading.value = true;
  try {
    // node.url 形如 '/api/projects/:id/files/:fid/download'，
    // apiClient.baseURL 默认 '/api'，需要剥掉前缀以匹配 baseURL
    let url = n.url;
    const base = (apiClient.defaults.baseURL ?? '/api').replace(/\/$/, '');
    if (base && url.startsWith(base + '/')) {
      url = url.slice(base.length);
    }
    const resp = await apiClient.get(url, { responseType: 'arraybuffer' });
    const arrayBuffer = resp.data as ArrayBuffer;
    // 动态 import 以减少首屏体积
    const mammoth = await import('mammoth');
    const result = await (mammoth as any).convertToHtml({ arrayBuffer });
    docxHtml.value = (result?.value as string) || '';
    if (!docxHtml.value) docxError.value = '解析结果为空';
  } catch (e: any) {
    console.error('[docx-preview]', e);
    docxError.value = e?.message || '解析失败';
  } finally {
    docxLoading.value = false;
  }
}

watch(
  () => node.value?.id,
  () => {
    const n = node.value;
    if (n && n.kind === 'file' && n.mime === DOCX_MIME) {
      void loadDocxPreview(n);
    } else {
      docxHtml.value = '';
      docxError.value = '';
      docxLoading.value = false;
    }
  },
  { immediate: true },
);

const breadcrumbText = computed(() =>
  node.value ? files.breadcrumb(node.value.id) : '',
);

const childList = computed<FileNode[]>(() => {
  if (!node.value || node.value.kind !== 'folder') return [];
  return files.children(node.value.id);
});

const renderedMd = computed<string>(() => {
  if (!node.value || node.value.kind !== 'file') return '';
  if (node.value.mime !== 'text/markdown') return '';
  const c = node.value.content ?? '';
  // marked 在某些版本同步返回 string，按同步处理
  return marked.parse(c, { async: false }) as string;
});

// ---- markdown 编辑模式 ----
const editing = ref(false);
const editingDraft = ref('');
const saving = ref(false);

/** 编辑模式实时预览（基于 draft） */
const editingRenderedMd = computed<string>(() => {
  return marked.parse(editingDraft.value ?? '', { async: false }) as string;
});

function enterEdit() {
  if (!node.value || node.value.kind !== 'file' || node.value.mime !== 'text/markdown') return;
  editingDraft.value = node.value.content ?? '';
  editing.value = true;
}

function cancelEdit() {
  editing.value = false;
  editingDraft.value = '';
}

async function saveEdit() {
  const n = node.value;
  if (!n || n.kind !== 'file' || n.mime !== 'text/markdown') return;
  const pid = files.projectId;
  if (!pid) {
    message.error('未关联项目，无法保存');
    return;
  }
  saving.value = true;
  try {
    const content = editingDraft.value ?? '';
    await apiClient.patch(`/projects/${pid}/files/${n.id}`, { content });
    files.writeContent(n.id, content);
    message.success('已保存');
    editing.value = false;
  } catch (e: any) {
    console.error('[md-save]', e);
    message.error('保存失败：' + (e?.message || '未知错误'));
  } finally {
    saving.value = false;
  }
}

// 切换文件时自动退出编辑模式
watch(
  () => node.value?.id,
  () => {
    editing.value = false;
    editingDraft.value = '';
  },
);

function fmtBytes(n?: number): string {
  if (n == null) return '-';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

function fmtTime(s?: string): string {
  if (!s) return '-';
  try { return new Date(s).toLocaleString('zh-CN', { hour12: false }); }
  catch { return s; }
}

function iconFor(n: FileNode): string {
  if (n.kind === 'folder') return '📁';
  const m = n.mime;
  if (m === 'text/markdown') return '📄';
  if (m === 'application/pdf') return '📑';
  if (m === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') return '📝';
  if (m === 'text/x-link') return '🔗';
  if (m && m.startsWith('image/')) return '🖼';
  return '📦';
}

function selectChild(c: FileNode) {
  files.selectFile(c.id);
}

function downloadAsFile(n: FileNode) {
  // 仅对内联文本可下载；二进制走占位 url
  if (n.content !== undefined) {
    const blob = new Blob([n.content], { type: n.mime ?? 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = n.name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 100);
  } else if (n.url) {
    window.open(n.url, '_blank');
  }
}
</script>

<template>
  <div class="pp-previewer">
    <!-- 空态 -->
    <div v-if="!node" class="pp-empty">
      <AEmpty description="← 在左侧选择一个文件预览" />
    </div>

    <template v-else>
      <!-- 顶部：breadcrumb + 文件名 + 元信息 -->
      <div class="pp-header">
        <div class="pp-breadcrumb">{{ breadcrumbText }}</div>
        <div class="pp-title">
          <span class="pp-title-icon">{{ iconFor(node) }}</span>
          <span class="pp-title-name">{{ node.name }}</span>
        </div>
        <div class="pp-meta">
          创建 {{ fmtTime(node.createdAt) }} · 更新 {{ fmtTime(node.updatedAt) }}
          <span v-if="node.kind === 'file' && node.size != null"> · {{ fmtBytes(node.size) }}</span>
        </div>
      </div>

      <!-- 内容区 -->
      <div class="pp-body">
        <!-- 文件夹：列出子项 -->
        <div v-if="node.kind === 'folder'" class="pp-folder">
          <div v-if="childList.length === 0" style="color:#aaa;text-align:center;padding:24px">
            （空文件夹）
          </div>
          <div v-else class="pp-folder-list">
            <div v-for="c in childList" :key="c.id" class="pp-folder-row" @click="selectChild(c)">
              <span style="margin-right:8px">{{ iconFor(c) }}</span>
              <span style="flex:1">{{ c.name }}</span>
              <span style="color:#aaa;font-size:12px">
                {{ c.kind === 'file' ? fmtBytes(c.size) : '文件夹' }}
              </span>
            </div>
          </div>
        </div>

        <!-- markdown -->
        <div v-else-if="node.mime === 'text/markdown'" class="pp-md-wrap">
          <div class="pp-md-toolbar">
            <template v-if="!editing">
              <AButton size="small" @click="enterEdit">✏️ 编辑</AButton>
            </template>
            <template v-else>
              <AButton size="small" type="primary" :loading="saving" @click="saveEdit">💾 保存</AButton>
              <AButton size="small" :disabled="saving" @click="cancelEdit">↩️ 取消</AButton>
              <span class="pp-md-tip">左侧编辑 raw markdown，右侧实时预览</span>
            </template>
          </div>
          <div v-if="!editing" class="preview-md" v-html="renderedMd" />
          <div v-else class="pp-md-edit">
            <ATextarea
              v-model:value="editingDraft"
              class="pp-md-textarea"
              :auto-size="false"
              spellcheck="false"
            />
            <div class="preview-md pp-md-livepreview" v-html="editingRenderedMd" />
          </div>
        </div>

        <!-- 图片 -->
        <div v-else-if="node.mime && node.mime.startsWith('image/')" style="text-align:center;padding:16px">
          <img :src="node.url ?? ''" :alt="node.name"
               style="max-width:100%;max-height:70vh;border-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,.1)" />
          <div v-if="!node.url" style="color:#aaa;font-size:12px;margin-top:8px">（未提供图片 URL）</div>
        </div>

        <!-- text/plain -->
        <pre v-else-if="node.mime === 'text/plain'" class="pp-pre">{{ node.content ?? '' }}</pre>

        <!-- application/json -->
        <pre v-else-if="node.mime === 'application/json'" class="pp-pre">{{ node.content ?? '' }}</pre>

        <!-- docx：mammoth 内嵌预览 -->
        <div v-else-if="node.mime === DOCX_MIME" class="pp-docx-wrap">
          <div v-if="docxLoading" class="pp-binary">
            <ASpin />
            <p style="color:#888;font-size:13px;margin-top:12px">正在解析 .docx ...</p>
          </div>
          <div v-else-if="docxError" class="pp-binary">
            <p>📝 <strong>{{ node.name }}</strong></p>
            <p style="color:#c0392b;font-size:13px">预览失败：{{ docxError }}</p>
            <p style="color:#888;font-size:12px">大小：{{ fmtBytes(node.size) }}</p>
            <AButton type="primary" @click="downloadAsFile(node)">下载</AButton>
          </div>
          <div v-else class="preview-docx" v-html="docxHtml" />
        </div>

        <!-- pdf：元信息 + 下载 -->
        <div v-else-if="node.mime === 'application/pdf'" class="pp-binary">
          <p>{{ iconFor(node) }} <strong>{{ node.name }}</strong></p>
          <p style="color:#888;font-size:13px">
            类型：PDF · 大小：{{ fmtBytes(node.size) }}
          </p>
          <AButton type="primary" @click="downloadAsFile(node)">下载</AButton>
        </div>

        <!-- 链接 -->
        <div v-else-if="node.mime === 'text/x-link'" class="pp-binary">
          <p>{{ node.name }}</p>
          <p v-if="node.url" style="color:#888;font-size:13px;word-break:break-all">{{ node.url }}</p>
          <a v-if="node.url" :href="node.url" target="_blank" rel="noopener noreferrer">
            <AButton type="primary">🔗 打开外部链接 →</AButton>
          </a>
        </div>

        <!-- 兜底 -->
        <div v-else class="pp-binary">
          <p>{{ iconFor(node) }} {{ node.name }}</p>
          <p style="color:#888;font-size:13px">类型：{{ node.mime ?? '未知' }}</p>
          <AButton @click="downloadAsFile(node)" :disabled="!node.content && !node.url">下载</AButton>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.pp-previewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  overflow: hidden;
}
.pp-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pp-header {
  padding: 10px 14px;
  border-bottom: 1px solid #eee;
  background: #fafafa;
}
.pp-breadcrumb {
  font-size: 11px;
  color: #999;
  word-break: break-all;
}
.pp-title {
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.pp-title-icon { font-size: 16px; }
.pp-title-name { font-size: 14px; font-weight: 600; }
.pp-meta {
  margin-top: 2px;
  color: #aaa;
  font-size: 11px;
}
.pp-body {
  flex: 1;
  overflow: auto;
}
.pp-folder { padding: 8px; }
.pp-folder-list { display: flex; flex-direction: column; }
.pp-folder-row {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.pp-folder-row:hover { background: #f5f5f5; }

.pp-md-wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.pp-md-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
  flex-shrink: 0;
}
.pp-md-tip {
  margin-left: 8px;
  color: #999;
  font-size: 12px;
}
.pp-md-edit {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 0;
  overflow: hidden;
}
.pp-md-textarea {
  border: none !important;
  border-right: 1px solid #f0f0f0 !important;
  border-radius: 0 !important;
  resize: none !important;
  height: 100% !important;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
  font-size: 13px !important;
  line-height: 1.6 !important;
  padding: 12px 14px !important;
  box-shadow: none !important;
  background: #fcfcfc;
}
.pp-md-textarea:focus {
  box-shadow: none !important;
  border-right: 1px solid #1677ff !important;
}
.pp-md-livepreview {
  overflow: auto;
  background: #fff;
}

.preview-md {
  padding: 16px 20px;
  font-size: 14px;
  line-height: 1.7;
  color: #1f2937;
  overflow: auto;
}
.preview-md :deep(h1),
.preview-md :deep(h2),
.preview-md :deep(h3) {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
}
.preview-md :deep(h1) { font-size: 22px; }
.preview-md :deep(h2) { font-size: 18px; }
.preview-md :deep(h3) { font-size: 16px; }
.preview-md :deep(p) { margin: 8px 0; }
.preview-md :deep(ul),
.preview-md :deep(ol) { padding-left: 24px; }
.preview-md :deep(code) {
  background: #f3f4f6;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 12px;
}
.preview-md :deep(pre) {
  background: #1f2937;
  color: #f9fafb;
  padding: 12px;
  border-radius: 6px;
  overflow: auto;
  font-size: 12px;
}
.preview-md :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
}
.preview-md :deep(blockquote) {
  border-left: 3px solid #d1d5db;
  padding: 4px 12px;
  color: #6b7280;
  margin: 8px 0;
}
.preview-md :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}
.preview-md :deep(th),
.preview-md :deep(td) {
  border: 1px solid #e5e7eb;
  padding: 6px 8px;
  font-size: 13px;
}

.pp-pre {
  padding: 16px 20px;
  font-size: 13px;
  background: #fafafa;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
.pp-binary {
  padding: 24px;
  text-align: center;
}
.pp-binary p { margin: 8px 0; }

.pp-docx-wrap { height: 100%; }
.preview-docx {
  padding: 20px 28px;
  font-size: 14px;
  line-height: 1.75;
  color: #1f2937;
  font-family: "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
.preview-docx :deep(h1),
.preview-docx :deep(h2),
.preview-docx :deep(h3),
.preview-docx :deep(h4) {
  margin-top: 18px;
  margin-bottom: 10px;
  font-weight: 600;
  line-height: 1.4;
}
.preview-docx :deep(h1) { font-size: 24px; }
.preview-docx :deep(h2) { font-size: 20px; }
.preview-docx :deep(h3) { font-size: 17px; }
.preview-docx :deep(h4) { font-size: 15px; }
.preview-docx :deep(p) {
  margin: 8px 0;
  line-height: 1.75;
}
.preview-docx :deep(ul),
.preview-docx :deep(ol) {
  padding-left: 28px;
  margin: 8px 0;
}
.preview-docx :deep(li) { margin: 4px 0; }
.preview-docx :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}
.preview-docx :deep(th),
.preview-docx :deep(td) {
  border: 1px solid #d9d9d9;
  padding: 6px 10px;
  font-size: 13px;
  vertical-align: top;
}
.preview-docx :deep(th) {
  background: #fafafa;
  font-weight: 600;
}
.preview-docx :deep(img) {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 8px 0;
}
.preview-docx :deep(strong) { font-weight: 600; }
.preview-docx :deep(em) { font-style: italic; }
.preview-docx :deep(a) { color: #1677ff; text-decoration: underline; }
</style>
