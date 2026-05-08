<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRoute } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { disclosureApi } from '@/api/disclosure';
import { useAuthStore } from '@/stores/auth';
import ClaimTierSelector from '@/components/disclosure/ClaimTierSelector.vue';
import TiptapEditor from '@/components/disclosure/TiptapEditor.vue';
import ReadonlyBanner from '@/components/common/ReadonlyBanner.vue';
import message from 'ant-design-vue/es/message';
import { exportDocx } from '@/utils/exportDocx';
import type { Project, ClaimTier } from '@/types';

const route = useRoute();
const auth = useAuthStore();

const project = ref<Project | null>(null);
const tier = ref<ClaimTier>('medium');
const body = ref<string>('');
const exporting = ref(false);

const isReadonly = computed(() => auth.role === 'admin');

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

async function handleExport() {
  if (!project.value) return;
  exporting.value = true;
  try {
    await exportDocx(project.value, tier.value);
    message.success('交底书已下载');
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    message.error(`导出失败：${msg}`);
  } finally {
    exporting.value = false;
  }
}
</script>

<template>
  <ReadonlyBanner :show="isReadonly" />
  <a-page-header :title="`项目 · ${project?.title ?? ''}`" sub-title="交底书编辑 · 三档独权切换" />

  <ClaimTierSelector v-if="project?.disclosure"
                     :claims="project.disclosure.claims"
                     :model-value="tier"
                     :readonly="isReadonly"
                     @update:model-value="changeTier" />

  <a-divider />

  <TiptapEditor v-model="body" :readonly="isReadonly" />

  <div style="margin-top:24px;display:flex;gap:12px;justify-content:flex-start">
    <a-space>
      <a-button @click="copyMarkdown">复制 Markdown</a-button>
      <a-button type="primary" :loading="exporting" @click="handleExport">导出 docx</a-button>
    </a-space>
  </div>
</template>
