<script setup lang="ts">
import { ref, reactive, computed } from 'vue';
import { useRouter } from 'vue-router';
import AProgress from 'ant-design-vue/es/progress';
import message from 'ant-design-vue/es/message';
import { projectsApi } from '@/api/projects';
import { useAuthStore } from '@/stores/auth';
import type { Domain, ProjectStage, ProjectGoal, Attachment } from '@/types';

defineProps<{ open: boolean }>();
const emit = defineEmits<{ (e: 'update:open', v: boolean): void; (e: 'created', id: string): void }>();

const router = useRouter();
const auth = useAuthStore();
const submitting = ref(false);

const form = reactive({
  title: '',
  domain: 'other' as Domain,
  customDomain: '',
  stage: 'idea' as ProjectStage,
  goal: 'full_disclosure' as ProjectGoal,
  notes: '',
});

const attachments = ref<Attachment[]>([]);

const DOMAINS: { value: Domain; label: string }[] = [
  { value: 'cryptography', label: '密码学' },
  { value: 'infosec', label: '信息安全' },
  { value: 'ai', label: '人工智能' },
  { value: 'other', label: '其他（自填）' },
];

const STAGES: { value: ProjectStage; label: string; icon: string }[] = [
  { value: 'idea',      label: '只是创意 · 还在脑子里', icon: '💡' },
  { value: 'prototype', label: '已有原型/Demo',         icon: '🛠️' },
  { value: 'deployed',  label: '已落地/上线',           icon: '🚀' },
];

const GOALS: { value: ProjectGoal; label: string; desc: string }[] = [
  { value: 'search_only',      label: '先看下值不值得申请', desc: '只跑现有技术检索 + 初步专利性判断' },
  { value: 'full_disclosure',  label: '完整专利交底书',     desc: '跑全流程，最终输出 .docx' },
  { value: 'specific_section', label: '特定章节或问题',      desc: '在 AI 对话中告诉助手具体要什么' },
];

const attachmentCount = computed(() => attachments.value.length);

// v0.15-D: 批传进度（复用 v0.14-B 视觉风格）
const uploadIndex = ref(0);
const uploadTotal = ref(0);
const uploadCurrentName = ref('');
const recentlyAddedFlash = ref(0);  // v0.31: 每次新文件入队 +1 触发列表入场动画
const uploading = computed(() => uploadTotal.value > 0 && uploadIndex.value < uploadTotal.value);
const uploadPercent = computed(() =>
  uploadTotal.value > 0 ? Math.round((uploadIndex.value / uploadTotal.value) * 100) : 0,
);

function genId() { return `att-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`; }

function isTextLike(name: string, mime: string): boolean {
  const lower = name.toLowerCase();
  if (lower.endsWith('.md') || lower.endsWith('.txt') || lower.endsWith('.json')) return true;
  if (lower.endsWith('.py') || lower.endsWith('.js') || lower.endsWith('.ts')) return true;
  if (lower.endsWith('.csv') || lower.endsWith('.yml') || lower.endsWith('.yaml')) return true;
  if (mime.startsWith('text/') || mime === 'application/json') return true;
  return false;
}

function isZipLike(name: string, mime: string): boolean {
  const lower = name.toLowerCase();
  return lower.endsWith('.zip') || mime === 'application/zip' || mime === 'application/x-zip-compressed';
}

/** v0.31: 推断 mime（office / 压缩 / 图片 等） */
function inferMimeByName(name: string, fallback: string): string {
  const l = name.toLowerCase();
  if (l.endsWith('.docx')) return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  if (l.endsWith('.doc'))  return 'application/msword';
  if (l.endsWith('.xlsx')) return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
  if (l.endsWith('.xls'))  return 'application/vnd.ms-excel';
  if (l.endsWith('.pptx')) return 'application/vnd.openxmlformats-officedocument.presentationml.presentation';
  if (l.endsWith('.ppt'))  return 'application/vnd.ms-powerpoint';
  if (l.endsWith('.csv'))  return 'text/csv';
  if (l.endsWith('.zip'))  return 'application/zip';
  if (l.endsWith('.pdf'))  return 'application/pdf';
  return fallback || 'application/octet-stream';
}

async function readAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onerror = () => reject(r.error);
    r.onload = () => resolve(String(r.result ?? ''));
    r.readAsText(file);
  });
}

function onUploadChange(info: { fileList: { uid: string }[] }) {
  if (info?.fileList?.length && uploadTotal.value === 0) {
    uploadTotal.value = info.fileList.length;
    uploadIndex.value = 0;
  }
}

// v0.35.3: 保留二进制原 File 对象，报门后用 multipart 传到 /files/upload
// 文本类仍走 attachments JSON（后端 create_project 把 content 存到 FileNode.content）
const pendingBinaries = new Map<string, File>();   // attachment id → File

/** v0.31: 通用入队，单文件 → attachment，自动加视觉脉动 */
async function _enqueueAttachment(file: File, sourceTag = '') {
  const mime = inferMimeByName(file.name, file.type || '');
  let content: string | undefined;
  const isText = isTextLike(file.name, mime) && file.size <= 2 * 1024 * 1024;
  if (isText) {
    try { content = await readAsText(file); } catch { /* 忽略 */ }
  }
  const attId = genId();
  attachments.value.push({
    id: attId,
    type: 'file',
    name: sourceTag ? `${sourceTag}/${file.name}` : file.name,
    size: file.size,
    mime,
    content,
    addedAt: new Date().toISOString(),
  });
  // v0.35.3: 二进制（pdf/office/图片 etc）保留 File 对象，报门后走 multipart
  if (!isText) {
    pendingBinaries.set(attId, file);
  }
  recentlyAddedFlash.value += 1;
}

async function beforeUpload(file: File): Promise<boolean> {
  uploadCurrentName.value = file.name;
  if (uploadTotal.value === 0) uploadTotal.value = 1;
  const mime = inferMimeByName(file.name, file.type || '');

  // v0.31: 压缩包自动解压（仅 .zip；最多展开 50 个文件，单文件 ≤ 5MB）
  if (isZipLike(file.name, mime)) {
    try {
      const JSZip = (await import('jszip')).default;
      const zip = await JSZip.loadAsync(file);
      const entries = Object.values(zip.files).filter(f => !f.dir);
      let extracted = 0;
      for (const entry of entries) {
        if (extracted >= 50) break;
        // skip junk
        if (entry.name.startsWith('__MACOSX/') || entry.name.endsWith('/.DS_Store')) continue;
        const blob = await entry.async('blob');
        if (blob.size > 5 * 1024 * 1024) continue;
        const baseName = entry.name.split('/').pop() || entry.name;
        const innerFile = new File([blob], baseName, {
          type: inferMimeByName(baseName, ''),
        });
        await _enqueueAttachment(innerFile, file.name.replace(/\.zip$/i, ''));
        extracted += 1;
      }
      message.success(`📦 解压「${file.name}」 → 加入 ${extracted} 个文件`);
    } catch (e) {
      message.error(`解压失败：${(e as Error).message}`);
      // 兜底：把 zip 自身入队
      await _enqueueAttachment(file);
    }
    uploadIndex.value += 1;
  } else {
    await _enqueueAttachment(file);
    uploadIndex.value += 1;
  }

  if (uploadIndex.value >= uploadTotal.value) {
    setTimeout(() => {
      if (uploadIndex.value >= uploadTotal.value) {
        uploadIndex.value = 0;
        uploadTotal.value = 0;
        uploadCurrentName.value = '';
      }
    }, 600);
  }
  return false;
}

function removeAt(id: string) {
  attachments.value = attachments.value.filter(a => a.id !== id);
  pendingBinaries.delete(id);
}

function fileIcon(mime?: string): string {
  if (!mime) return '📦';
  if (mime.startsWith('image/')) return '🖼️';
  if (mime.includes('pdf')) return '📑';
  // v0.31: office
  if (mime.includes('wordprocessingml') || mime === 'application/msword') return '📝';
  if (mime.includes('spreadsheetml') || mime === 'application/vnd.ms-excel') return '📊';
  if (mime.includes('presentationml') || mime === 'application/vnd.ms-powerpoint') return '📽️';
  if (mime === 'text/csv') return '📊';
  if (mime.includes('text/markdown') || mime.includes('plain')) return '📄';
  if (mime.includes('zip') || mime.includes('rar') || mime.includes('compressed')) return '🗜️';
  if (mime.includes('json') || mime.includes('javascript') || mime.includes('python')) return '💻';
  return '📦';
}

function fmtSize(b?: number): string {
  if (b == null) return '';
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

function reset() {
  form.title = '';
  form.domain = 'other';
  form.customDomain = '';
  form.stage = 'idea';
  form.goal = 'full_disclosure';
  form.notes = '';
  attachments.value = [];
  pendingBinaries.clear();
  uploadIndex.value = 0;
  uploadTotal.value = 0;
  uploadCurrentName.value = '';
}

async function onOk() {
  if (form.title.trim().length < 4) {
    message.warning('请填项目标题（至少 4 字）');
    return;
  }
  if (form.domain === 'other' && form.customDomain.trim().length < 2) {
    message.warning('选了"其他"请填写具体技术领域');
    return;
  }
  submitting.value = true;
  try {
    const domainShown = form.domain === 'other'
      ? form.customDomain.trim()
      : (DOMAINS.find(d => d.value === form.domain)?.label ?? form.domain);
    const description = form.notes.trim()
      || `领域=${domainShown}, 阶段=${form.stage}, 期望=${form.goal}（员工未填补充说明）`;
    // 仅文本类 attachment 走 JSON content；二进制不传（异步 multipart 上传）
    const textAttachments = attachments.value.filter(a => !pendingBinaries.has(a.id));
    const p = await projectsApi.create({
      title: form.title.trim(),
      description,
      domain: form.domain,
      customDomain: form.domain === 'other' ? form.customDomain.trim() : undefined,
      ownerId: auth.user!.id,
      attachments: textAttachments.length ? textAttachments : undefined,
    });

    // v0.35.4: 二进制 attachment 入队 → 立即跳转工作台 → 工作台异步上传 + chat 显示进度
    if (pendingBinaries.size > 0) {
      const { enqueueUploads } = await import('@/stores/uploadQueue');
      enqueueUploads(p.id, [...pendingBinaries.values()]);
    }

    message.success('已创建，进入项目工作台');
    emit('created', p.id);
    emit('update:open', false);
    reset();
    router.push(`/employee/projects/${p.id}/workbench?fresh=1`);
  } catch (e) {
    message.error('创建失败：' + (e as Error).message);
  } finally {
    submitting.value = false;
  }
}

function onCancel() {
  emit('update:open', false);
}
</script>

<template>
  <a-modal :open="open" @update:open="(v: boolean) => emit('update:open', v)"
           title="新建报门 · 启动专利挖掘"
           :width="780"
           wrap-class-name="pp-newproj-wrap"
           :ok-text="`确定 (${attachmentCount} 项资料)`"
           :ok-button-props="{ loading: submitting }"
           @ok="onOk" @cancel="onCancel" :mask-closable="false">

    <a-form layout="vertical">
      <!-- 大文件上传区（紧凑版 + 显式按钮 + 全局拖拽防御标记） -->
      <div class="pp-upload-hero" data-pp-dropzone>
        <div class="pp-upload-hero__head">
          <div>
            <h3 class="pp-upload-hero__title">📎 把和创意相关的资料拖到这里</h3>
            <p class="pp-upload-hero__sub">支持 Word / Excel / PPT / PDF / 图片 / 代码 / 压缩包（自动解压）</p>
          </div>
          <a-upload
            :multiple="true"
            :before-upload="beforeUpload"
            :show-upload-list="false"
            :disabled="uploading"
            @change="onUploadChange"
            accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.csv,.md,.txt,.json,.png,.jpg,.jpeg,.gif,.svg,.webp,.py,.js,.ts,.tsx,.yml,.yaml,.zip"
          >
            <a-button type="primary" :disabled="uploading" class="pp-upload-pick-btn">
              📁 选择文件
            </a-button>
          </a-upload>
        </div>
        <div
          class="pp-newproj-upload-wrap"
          :class="{ 'pp-newproj-upload-wrap--flash': recentlyAddedFlash > 0 }"
        >
          <a-upload-dragger
            class="pp-upload-dragger--compact"
            name="file"
            :multiple="true"
            :before-upload="beforeUpload"
            :show-upload-list="false"
            :disabled="uploading"
            @change="onUploadChange"
            accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.csv,.md,.txt,.json,.png,.jpg,.jpeg,.gif,.svg,.webp,.py,.js,.ts,.tsx,.yml,.yaml,.zip"
          >
            <p class="ant-upload-drag-icon" style="font-size:24px;margin:0 0 2px">📎</p>
            <p class="ant-upload-text" style="font-size:13px;margin:0">点击或拖拽文件到此区域（可多选；不识别格式不会被浏览器下载）</p>
          </a-upload-dragger>
          <!-- v0.15-D: 批传进度叠层 -->
          <div v-if="uploading" class="pp-newproj-progress-overlay">
            <div class="pp-newproj-progress-card">
              <div class="pp-newproj-progress-title">
                添加中 {{ uploadIndex }} / {{ uploadTotal }}
              </div>
              <div class="pp-newproj-progress-name" :title="uploadCurrentName">
                {{ uploadCurrentName || '准备中…' }}
              </div>
              <AProgress :percent="uploadPercent" size="small" status="active" />
            </div>
          </div>
        </div>

        <a-list v-if="attachmentCount" size="small" bordered :data-source="attachments"
                class="pp-attach-list" style="margin-top:10px"
                :key="recentlyAddedFlash">
          <template #renderItem="{ item }: { item: Attachment }">
            <a-list-item class="pp-attach-item">
              <template #actions>
                <a-button type="link" danger size="small" @click="removeAt(item.id)">移除</a-button>
              </template>
              <span style="margin-right:8px;font-size:16px">{{ fileIcon(item.mime) }}</span>
              <span style="margin-right:8px;font-weight:500">{{ item.name }}</span>
              <span style="color:#999;font-size:12px">{{ fmtSize(item.size) }}</span>
            </a-list-item>
          </template>
        </a-list>
      </div>

      <a-divider class="pp-divider--compact" />

      <a-form-item label="项目标题" required>
        <a-input v-model:value="form.title" placeholder="一句话描述你的创新点" :maxlength="60" show-count />
      </a-form-item>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="技术领域" required>
            <a-select v-model:value="form.domain">
              <a-select-option v-for="d in DOMAINS" :key="d.value" :value="d.value">{{ d.label }}</a-select-option>
            </a-select>
            <a-input v-if="form.domain === 'other'"
                     v-model:value="form.customDomain"
                     style="margin-top:8px"
                     placeholder="请输入具体领域，如：生物医药 / 机械设计 / 物联网…"
                     :maxlength="40" show-count />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="当前阶段" required>
            <a-select v-model:value="form.stage">
              <a-select-option v-for="s in STAGES" :key="s.value" :value="s.value">
                {{ s.icon }} {{ s.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item label="期望 AI 帮你做什么">
        <div class="pp-goal-grid">
          <label
            v-for="g in GOALS"
            :key="g.value"
            class="pp-goal-card"
            :class="{ 'pp-goal-card--active': form.goal === g.value }"
          >
            <input
              type="radio"
              name="pp-goal"
              :value="g.value"
              v-model="form.goal"
              class="pp-goal-card__input"
            />
            <span class="pp-goal-card__label">{{ g.label }}</span>
            <span class="pp-goal-card__desc">{{ g.desc }}</span>
          </label>
        </div>
      </a-form-item>

      <a-form-item label="补充说明（可选）">
        <a-textarea v-model:value="form.notes" :rows="2"
                    placeholder="比如：方案的核心区别、想规避哪家专利、特定章节细节…" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<style scoped>
/* 上传 hero 区：紧凑版（v0.30：让整个 modal 一屏不滚动） */
.pp-upload-hero {
  background: var(--pp-color-primary-soft);
  border: 1px dashed var(--pp-color-primary);
  border-radius: var(--pp-radius-md);
  padding: 10px 12px;
}
.pp-upload-hero__title {
  margin: 0 0 2px;
  font-size: 13px;
  font-weight: 600;
  color: var(--pp-color-text);
}
.pp-upload-hero__sub {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--pp-color-text-secondary);
}
/* v0.31: hero 头部 (标题 + 选择按钮) */
.pp-upload-hero__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--pp-space-3);
  margin-bottom: 6px;
}
.pp-upload-pick-btn {
  flex-shrink: 0;
}
/* v0.31: 拖入文件后的脉动反馈 */
@keyframes pp-flash-pulse {
  0% { box-shadow: 0 0 0 0 rgba(91, 108, 255, 0.45); }
  100% { box-shadow: 0 0 0 12px rgba(91, 108, 255, 0); }
}
.pp-newproj-upload-wrap--flash :deep(.ant-upload-drag) {
  animation: pp-flash-pulse 700ms ease-out;
  border-color: var(--pp-color-primary) !important;
  background: var(--pp-color-primary-soft) !important;
}
/* v0.31: 拖拽悬停时 dragger 边框变品牌色（antd 默认是主色，这里强化） */
:deep(.pp-upload-dragger--compact .ant-upload-drag-hover),
:deep(.pp-upload-dragger--compact .ant-upload-drag:hover) {
  border-color: var(--pp-color-primary) !important;
  background: var(--pp-color-primary-soft) !important;
}
/* v0.31: 附件列表入场动画 */
@keyframes pp-attach-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
.pp-attach-list :deep(.ant-list-item) {
  animation: pp-attach-in 200ms ease-out;
}
/* 拖拽区缩矮 */
:deep(.pp-upload-dragger--compact .ant-upload-drag) {
  padding: 12px 8px !important;
  border-radius: var(--pp-radius-sm) !important;
}
:deep(.pp-upload-dragger--compact .ant-upload-btn) {
  padding: 0 !important;
}
/* divider 更紧 */
:deep(.pp-divider--compact) {
  margin: 8px 0 !important;
}
/* v0.30：横排 goal 卡片 — 替代原 a-radio 三行布局 */
.pp-goal-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.pp-goal-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  border: 1.5px solid var(--pp-color-border);
  border-radius: var(--pp-radius-md);
  cursor: pointer;
  background: var(--pp-color-surface);
  transition: all 0.15s ease;
  min-height: 56px;
}
.pp-goal-card:hover {
  border-color: var(--pp-color-primary);
  background: var(--pp-color-primary-soft);
}
.pp-goal-card--active {
  border-color: var(--pp-color-primary);
  background: var(--pp-color-primary-soft);
  box-shadow: 0 0 0 3px rgba(91, 108, 255, 0.12);
}
.pp-goal-card__input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.pp-goal-card__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--pp-color-text);
  line-height: 1.2;
}
.pp-goal-card--active .pp-goal-card__label {
  color: var(--pp-color-primary);
}
.pp-goal-card__desc {
  font-size: 11.5px;
  color: var(--pp-color-text-secondary);
  line-height: 1.35;
}
@media (max-width: 640px) {
  .pp-goal-grid { grid-template-columns: 1fr; }
}
/* form-item 间距收紧 */
:deep(.ant-form-item) { margin-bottom: 12px !important; }
:deep(.ant-form-item-label) { padding-bottom: 2px !important; }
:deep(.ant-form-item-label > label) { height: 22px !important; font-size: 13px !important; }
.pp-newproj-upload-wrap {
  position: relative;
}
/* 进度叠层：用 token 色和 radius */
.pp-newproj-progress-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.88);
  border-radius: var(--pp-radius-md);
  z-index: 6;
  backdrop-filter: blur(2px);
}
.pp-newproj-progress-card {
  background: var(--pp-color-surface);
  border: 1px solid var(--pp-color-border-soft);
  border-radius: var(--pp-radius-lg);
  padding: 14px 16px;
  width: min(85%, 320px);
  box-shadow: var(--pp-shadow-lg);
}
.pp-newproj-progress-title {
  font-size: var(--pp-font-size-xs);
  color: var(--pp-color-text-secondary);
  font-weight: var(--pp-font-weight-semibold);
  margin-bottom: 4px;
}
.pp-newproj-progress-name {
  font-size: var(--pp-font-size-sm);
  color: var(--pp-color-text);
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

<!-- 非 scoped 全局样式：a-modal 由 ant-design-vue 通过 teleport 渲染到 body -->
<style>
/* modal 容器：radius-lg + shadow-xl + 顶部 24px 渐变条 */
.pp-newproj-wrap .ant-modal-content {
  border-radius: var(--pp-radius-lg);
  box-shadow: var(--pp-shadow-xl);
  overflow: hidden;
  padding: 0;
  position: relative;
}
.pp-newproj-wrap .ant-modal-content::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 24px;
  background: linear-gradient(135deg, var(--pp-color-primary) 0%, #8B5CF6 50%, #EC4899 100%);
  z-index: 1;
  pointer-events: none;
}
/* v0.29 fix: close 按钮完全收进 24px 渐变条内，避免下半与 modal-header 标题重叠/被切 */
.pp-newproj-wrap .ant-modal-close {
  z-index: 10;
  top: 0 !important;
  right: 0 !important;
  width: 48px !important;
  height: 24px !important;     /* 与渐变条同高，整体落在渐变条内 */
  border-radius: 0 var(--pp-radius-lg) 0 var(--pp-radius-sm);
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  color: #fff;
  padding: 0 !important;
  margin: 0 !important;
}
.pp-newproj-wrap .ant-modal-close-x {
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: #fff !important;
  font-size: 14px;
  line-height: 1;
}
.pp-newproj-wrap .ant-modal-close .ant-modal-close-icon,
.pp-newproj-wrap .ant-modal-close svg {
  font-size: 14px;
  color: #fff;
}
.pp-newproj-wrap .ant-modal-close:hover {
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
}
.pp-newproj-wrap .ant-modal-header {
  padding: 30px 20px 8px;       /* 24px 渐变条 + 6px 喘息 */
  margin-bottom: 0;
  border-bottom: 1px solid var(--pp-color-border-soft);
  border-radius: 0;
}
.pp-newproj-wrap .ant-modal-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--pp-color-text);
}
.pp-newproj-wrap .ant-modal-body {
  padding: 14px 20px;
  max-height: calc(92vh - 88px);  /* 防溢出但尽量一屏；超时滚动 */
  overflow-y: auto;
}
.pp-newproj-wrap .ant-modal-footer {
  padding: 10px 20px;
  border-top: 1px solid var(--pp-color-border-soft);
}

/* 表单分组分隔 divider */
.pp-newproj-wrap .ant-divider {
  border-color: var(--pp-color-border-soft);
  margin: var(--pp-space-4) 0;
}

/* a-select-option 内 stage 选项：选中状态浅紫底 + primary 边 */
.pp-newproj-wrap .ant-select-item-option-selected:not(.ant-select-item-option-disabled) {
  background: var(--pp-color-primary-soft);
  color: var(--pp-color-primary);
  font-weight: var(--pp-font-weight-medium);
}
.pp-newproj-wrap .ant-select-item-option-active:not(.ant-select-item-option-disabled) {
  background: var(--pp-color-primary-soft-hover);
}
</style>
