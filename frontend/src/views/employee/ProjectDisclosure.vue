<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { disclosureApi } from '@/api/disclosure';
import { useAuthStore } from '@/stores/auth';
import ClaimTierSelector from '@/components/disclosure/ClaimTierSelector.vue';
import TiptapEditor from '@/components/disclosure/TiptapEditor.vue';
import ReadonlyBanner from '@/components/common/ReadonlyBanner.vue';
import { message, Modal } from 'ant-design-vue';
import type { Project, ClaimTier } from '@/types';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const project = ref<Project | null>(null);
const tier = ref<ClaimTier>('medium');
const body = ref<string>('');
const submitting = ref(false);

const isReadonly = computed(() => auth.role === 'admin');
const isSubmitted = computed(() => project.value?.status === 'submitted');

onMounted(async () => {
  const id = route.params.id as string;
  project.value = await projectsApi.get(id);
  if (project.value?.disclosure) {
    body.value = renderHtml(project.value.disclosure);
    const broad = project.value.disclosure.claims.find(c => c.tier === 'broad');
    if (broad) tier.value = 'medium'; // 默认中档
  }
});

function renderHtml(d: { technicalField: string; background: string; summary: string; embodiments: string }): string {
  return `<h2>技术领域</h2><p>${d.technicalField}</p>
          <h2>背景技术</h2><p>${d.background}</p>
          <h2>发明内容</h2><p>${d.summary}</p>
          <h2>具体实施方式</h2><p>${d.embodiments}</p>`;
}

async function changeTier(t: ClaimTier) {
  tier.value = t;
  if (!project.value) return;
  const d = await disclosureApi.selectClaimTier(project.value.id, t);
  body.value = renderHtml({
    technicalField: d.technicalField,
    background: d.background,
    summary: d.summary,
    embodiments: d.embodiments,
  });
  message.info(`已切换到 ${t} 档独权`);
}

function copyMarkdown() {
  const md = body.value
    .replace(/<h2>/g, '\n## ').replace(/<\/h2>/g, '\n')
    .replace(/<p>/g, '').replace(/<\/p>/g, '\n')
    .replace(/<[^>]+>/g, '');
  navigator.clipboard.writeText(md);
  message.success('Markdown 已复制到剪贴板');
}

function exportDocx() {
  message.info('v0.2 支持真实 docx 导出，目前已下载占位 .docx 文件（演示）');
}

async function submit() {
  if (!project.value) return;
  Modal.confirm({
    title: '确认提交存档？',
    content: '提交后将由 IP 部门线下处理；可以"取消提交"回退编辑。',
    async onOk() {
      submitting.value = true;
      try {
        await projectsApi.submit(project.value!.id);
        project.value!.status = 'submitted';
        message.success('已提交至 IP 部门，将由专员线下处理');
      } finally { submitting.value = false; }
    },
  });
}

async function unsubmit() {
  if (!project.value) return;
  await projectsApi.unsubmit(project.value.id);
  project.value.status = 'reporting';
  message.info('已取消提交，可继续编辑');
}
</script>

<template>
  <ReadonlyBanner :show="isReadonly" />
  <a-page-header :title="project?.title ?? ''" sub-title="交底书编辑 · 三档独权切换" />

  <ClaimTierSelector v-if="project?.disclosure"
                     :claims="project.disclosure.claims"
                     :model-value="tier"
                     :readonly="isReadonly || isSubmitted"
                     @update:model-value="changeTier" />

  <a-divider />

  <TiptapEditor v-model="body" :readonly="isReadonly || isSubmitted" />

  <div style="margin-top:24px;display:flex;gap:12px;justify-content:space-between">
    <a-space>
      <a-button @click="copyMarkdown">复制 Markdown</a-button>
      <a-button @click="exportDocx">导出 docx</a-button>
    </a-space>
    <a-space v-if="!isReadonly">
      <a-button v-if="isSubmitted" danger @click="unsubmit">取消提交，回退编辑</a-button>
      <a-button v-else type="primary" :loading="submitting" @click="submit">提交存档 →</a-button>
    </a-space>
  </div>
</template>
