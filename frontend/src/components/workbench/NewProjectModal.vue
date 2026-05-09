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
const uploading = computed(() => uploadTotal.value > 0 && uploadIndex.value < uploadTotal.value);
const uploadPercent = computed(() =>
  uploadTotal.value > 0 ? Math.round((uploadIndex.value / uploadTotal.value) * 100) : 0,
);

function genId() { return `att-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`; }

function isTextLike(name: string, mime: string): boolean {
  const lower = name.toLowerCase();
  if (lower.endsWith('.md') || lower.endsWith('.txt') || lower.endsWith('.json')) return true;
  if (lower.endsWith('.py') || lower.endsWith('.js') || lower.endsWith('.ts')) return true;
  if (mime.startsWith('text/') || mime === 'application/json') return true;
  return false;
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
  // antd 串行调 beforeUpload 时，先用 fileList.length 设置 total（用户一次选多文件场景）
  if (info?.fileList?.length && uploadTotal.value === 0) {
    uploadTotal.value = info.fileList.length;
    uploadIndex.value = 0;
  }
}

async function beforeUpload(file: File): Promise<boolean> {
  uploadCurrentName.value = file.name;
  // 单文件场景下 fileList 没事先赋 total，用流式累加
  if (uploadTotal.value === 0) uploadTotal.value = 1;
  const mime = file.type || 'application/octet-stream';
  let content: string | undefined;
  if (isTextLike(file.name, mime) && file.size <= 2 * 1024 * 1024) {
    try { content = await readAsText(file); } catch { /* 忽略 */ }
  }
  attachments.value.push({
    id: genId(), type: 'file',
    name: file.name, size: file.size, mime,
    content,
    addedAt: new Date().toISOString(),
  });
  uploadIndex.value += 1;
  // 全部完成时清状态
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
}

function fileIcon(mime?: string): string {
  if (!mime) return '📦';
  if (mime.startsWith('image/')) return '🖼️';
  if (mime.includes('pdf')) return '📑';
  if (mime.includes('word') || mime.includes('officedocument')) return '📝';
  if (mime.includes('text/markdown') || mime.includes('plain')) return '📄';
  if (mime.includes('zip') || mime.includes('rar')) return '🗜️';
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
    const p = await projectsApi.create({
      title: form.title.trim(),
      description,
      domain: form.domain,
      customDomain: form.domain === 'other' ? form.customDomain.trim() : undefined,
      ownerId: auth.user!.id,
      attachments: attachments.value.length ? attachments.value : undefined,
    });
    message.success('已创建，进入项目工作台');
    emit('created', p.id);
    emit('update:open', false);
    reset();
    router.push(`/employee/projects/${p.id}/workbench`);
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
           title="新建创新报门（提交你的创意，启动专利挖掘）" width="780" :ok-text="`确定 (${attachmentCount} 项资料)`"
           :ok-button-props="{ loading: submitting }"
           @ok="onOk" @cancel="onCancel" :mask-closable="false"
           class="pp-newproj-modal"
           wrap-class-name="pp-newproj-wrap">

    <a-form layout="vertical">
      <!-- 大文件上传区 -->
      <div class="pp-upload-hero">
        <h3 style="margin:0 0 4px 0;font-size:15px">📎 你可以把和创意有关的文档、代码、图像等各种资料都扔到这里</h3>
        <p style="color:#888;font-size:12px;margin:0 0 12px">PDF / Word / 代码 / 图片 / 设计稿都行；越多越好，AI 会自动分析。</p>
        <div class="pp-newproj-upload-wrap">
          <a-upload-dragger
            name="file"
            :multiple="true"
            :before-upload="beforeUpload"
            :show-upload-list="false"
            :disabled="uploading"
            @change="onUploadChange"
            accept=".pdf,.doc,.docx,.md,.txt,.png,.jpg,.jpeg,.svg,.json,.py,.js,.ts,.zip,.tar,.gz"
          >
            <p class="ant-upload-drag-icon" style="font-size:36px;margin:8px 0">📎</p>
            <p class="ant-upload-text">点击或拖拽文件到此区域</p>
            <p class="ant-upload-hint">支持 pdf / doc / docx / md / txt / 图片 / 代码 / 压缩包，可多选</p>
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

        <a-list v-if="attachmentCount" size="small" bordered :data-source="attachments" style="margin-top:12px">
          <template #renderItem="{ item }: { item: Attachment }">
            <a-list-item>
              <template #actions>
                <a-button type="link" danger size="small" @click="removeAt(item.id)">移除</a-button>
              </template>
              <span style="margin-right:8px">{{ fileIcon(item.mime) }}</span>
              <span style="margin-right:8px">{{ item.name }}</span>
              <span style="color:#999;font-size:12px">{{ fmtSize(item.size) }}</span>
            </a-list-item>
          </template>
        </a-list>
      </div>

      <a-divider />

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
        <a-radio-group v-model:value="form.goal">
          <a-space direction="vertical" style="width:100%">
            <a-radio v-for="g in GOALS" :key="g.value" :value="g.value">
              <strong>{{ g.label }}</strong>
              <span style="color:#888;font-size:12px;margin-left:8px">{{ g.desc }}</span>
            </a-radio>
          </a-space>
        </a-radio-group>
      </a-form-item>

      <a-form-item label="补充说明（可选）">
        <a-textarea v-model:value="form.notes" :rows="3"
                    placeholder="比如：方案的核心区别、想规避哪家专利、特定章节细节…" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<style scoped>
/* 上传 hero 区：primary-soft 底 + dashed primary 边 + radius-lg */
.pp-upload-hero {
  background: var(--pp-color-primary-soft);
  border: 1px dashed var(--pp-color-primary);
  border-radius: var(--pp-radius-lg);
  padding: var(--pp-space-4);
}
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
  padding: calc(24px + var(--pp-space-4)) var(--pp-space-5) var(--pp-space-3);
  margin-bottom: 0;
  border-bottom: 1px solid var(--pp-color-border-soft);
  border-radius: 0;
}
.pp-newproj-wrap .ant-modal-title {
  font-size: var(--pp-font-size-lg);
  font-weight: var(--pp-font-weight-semibold);
  color: var(--pp-color-text);
}
.pp-newproj-wrap .ant-modal-body {
  padding: var(--pp-space-5);
}
.pp-newproj-wrap .ant-modal-footer {
  padding: var(--pp-space-3) var(--pp-space-5);
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
