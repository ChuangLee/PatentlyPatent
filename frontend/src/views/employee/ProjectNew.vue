<script setup lang="ts">
import { reactive, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { useAuthStore } from '@/stores/auth';
import { message } from 'ant-design-vue';
import type { Domain, Attachment } from '@/types';

const router = useRouter();
const auth = useAuthStore();
const submitting = ref(false);

const form = reactive({
  title: '',
  description: '',
  domain: 'other' as Domain,
});

const DOMAINS: { value: Domain; label: string }[] = [
  { value: 'cryptography', label: '密码学' },
  { value: 'infosec', label: '信息安全' },
  { value: 'ai', label: '人工智能' },
  { value: 'other', label: '其他' },
];

// 资料状态
const attachments = ref<Attachment[]>([]);
const activeTab = ref<'file' | 'link' | 'note'>('file');

// 链接 tab
const linkUrl = ref('');
const linkTitle = ref('');

// 笔记 tab
const noteText = ref('');

function genId() {
  return `att-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function getExt(name: string): string {
  const idx = name.lastIndexOf('.');
  return idx >= 0 ? name.slice(idx + 1).toLowerCase() : '';
}

function formatSize(bytes?: number): string {
  if (bytes == null) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// 文件 tab：阻止真实上传，只把文件信息加入 attachments
function beforeUpload(file: File) {
  attachments.value.push({
    id: genId(),
    type: 'file',
    name: file.name,
    size: file.size,
    mime: file.type,
    addedAt: new Date().toISOString(),
  });
  // 返回 false 阻止 antd 上传
  return false;
}

function addLink() {
  const url = linkUrl.value.trim();
  if (!url) {
    message.warning('请填写 URL');
    return;
  }
  attachments.value.push({
    id: genId(),
    type: 'link',
    name: linkTitle.value.trim() || url,
    url,
    addedAt: new Date().toISOString(),
  });
  linkUrl.value = '';
  linkTitle.value = '';
}

function addNote() {
  const text = noteText.value.trim();
  if (!text) {
    message.warning('请输入笔记内容');
    return;
  }
  attachments.value.push({
    id: genId(),
    type: 'note',
    name: text.slice(0, 30),
    content: text,
    addedAt: new Date().toISOString(),
  });
  noteText.value = '';
}

function removeAttachment(id: string) {
  attachments.value = attachments.value.filter(a => a.id !== id);
}

const attachmentCount = computed(() => attachments.value.length);

async function submit() {
  if (!form.title.trim() || form.description.length < 30) {
    message.warning('标题不能为空，描述至少 30 字');
    return;
  }
  submitting.value = true;
  try {
    const p = await projectsApi.create({
      title: form.title,
      description: form.description,
      domain: form.domain,
      ownerId: auth.user!.id,
      attachments: attachments.value.length ? attachments.value : undefined,
    });
    message.success('已创建，进入 AI 引导对话');
    router.push(`/employee/projects/${p.id}/mining`);
  } catch (e) {
    message.error('创建失败：' + (e as Error).message);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <a-page-header title="新建创新报门" @back="router.back()" />

  <a-form layout="vertical" style="max-width:720px">
    <a-form-item label="项目标题（10–50 字）" required>
      <a-input v-model:value="form.title" placeholder="例：基于 SIMD 的 Kyber-512 NTT 优化"
               :maxlength="50" show-count />
    </a-form-item>

    <a-form-item label="技术领域" required>
      <a-select v-model:value="form.domain">
        <a-select-option v-for="d in DOMAINS" :key="d.value" :value="d.value">
          {{ d.label }}
        </a-select-option>
      </a-select>
    </a-form-item>

    <a-form-item label="一句话或几段描述（≥30 字，越详细 AI 引导越准）" required>
      <a-textarea v-model:value="form.description" :rows="6"
                  placeholder="例：我们在 ARM Cortex-M4 上对 Kyber-512 NTT 做了 SIMD 两路并行..." />
    </a-form-item>

    <a-divider>上传辅助资料（可选，越多越好）</a-divider>

    <a-tabs v-model:activeKey="activeTab">
      <a-tab-pane key="file" tab="文件">
        <a-upload-dragger
          name="file"
          :multiple="true"
          :before-upload="beforeUpload"
          :show-upload-list="false"
          accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
        >
          <p class="ant-upload-drag-icon" style="font-size:32px">📎</p>
          <p class="ant-upload-text">点击或拖拽文件到此区域</p>
          <p class="ant-upload-hint">支持 pdf / doc / docx / png / jpg，可多选</p>
        </a-upload-dragger>
      </a-tab-pane>

      <a-tab-pane key="link" tab="链接">
        <a-form layout="vertical">
          <a-form-item label="URL">
            <a-input v-model:value="linkUrl" placeholder="https://..." />
          </a-form-item>
          <a-form-item label="标题（选填）">
            <a-input v-model:value="linkTitle" placeholder="例：上下文背景论文" />
          </a-form-item>
          <a-button type="primary" ghost @click="addLink">添加链接</a-button>
        </a-form>
      </a-tab-pane>

      <a-tab-pane key="note" tab="笔记">
        <a-form layout="vertical">
          <a-form-item label="补充说明">
            <a-textarea v-model:value="noteText" :rows="4" placeholder="例：本方案与 X 方案的核心区别在于..." />
          </a-form-item>
          <a-button type="primary" ghost @click="addNote">添加笔记</a-button>
        </a-form>
      </a-tab-pane>
    </a-tabs>

    <div v-if="attachmentCount" style="margin-top:16px">
      <h4>已添加资料（{{ attachmentCount }}）</h4>
      <a-list size="small" bordered :data-source="attachments">
        <template #renderItem="{ item }">
          <a-list-item>
            <template #actions>
              <a-button type="link" danger size="small" @click="removeAttachment(item.id)">删除</a-button>
            </template>
            <template v-if="item.type === 'file'">
              <span style="margin-right:8px">📎</span>
              <span style="margin-right:8px">{{ item.name }}</span>
              <a-tag v-if="getExt(item.name)" color="blue">.{{ getExt(item.name) }}</a-tag>
              <span style="color:#999;margin-left:8px">{{ formatSize(item.size) }}</span>
            </template>
            <template v-else-if="item.type === 'link'">
              <span style="margin-right:8px">🔗</span>
              <span style="margin-right:8px">{{ item.name }}</span>
              <span style="color:#999;font-size:12px">{{ item.url }}</span>
            </template>
            <template v-else-if="item.type === 'note'">
              <span style="margin-right:8px">📝</span>
              <span>{{ (item.content ?? '').slice(0, 30) }}{{ (item.content ?? '').length > 30 ? '...' : '' }}</span>
            </template>
          </a-list-item>
        </template>
      </a-list>
    </div>

    <a-form-item style="margin-top:24px">
      <a-button type="primary" :loading="submitting" @click="submit">提交并进入 AI 引导 →</a-button>
    </a-form-item>
  </a-form>
</template>
