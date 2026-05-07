<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { useAuthStore } from '@/stores/auth';
import NewProjectModal from '@/components/workbench/NewProjectModal.vue';
import type { Project, ProjectStatus } from '@/types';

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const projects = ref<Project[]>([]);
const loading = ref(true);
const modalOpen = ref(false);

async function refresh() {
  loading.value = true;
  projects.value = await projectsApi.list({ ownerId: auth.user!.id });
  loading.value = false;
}

onMounted(() => {
  refresh();
  if (route.query.new === '1') {
    modalOpen.value = true;
    router.replace({ path: route.path, query: {} });
  }
});

watch(() => route.query.new, (v) => {
  if (v === '1') {
    modalOpen.value = true;
    router.replace({ path: route.path, query: {} });
  }
});

const STATUS_LABEL: Record<ProjectStatus, { text: string; color: string }> = {
  drafting:    { text: '草稿', color: 'default' },
  researching: { text: '挖掘中', color: 'processing' },
  reporting:   { text: '检索完成', color: 'cyan' },
  completed:   { text: '已完成（已导出）', color: 'success' },
};

function go(p: Project) {
  router.push(`/employee/projects/${p.id}/workbench`);
}
</script>

<template>
  <a-page-header title="我的创新项目" sub-title="把工作中发现的创新点报上来，AI 帮你拆解并起草交底书" />

  <a-button type="primary" size="large" style="margin-bottom:24px" @click="modalOpen = true">
    ✨ 新建报门（提交创意，启动 AI 专利挖掘）
  </a-button>

  <a-spin :spinning="loading">
    <a-empty v-if="!loading && projects.length === 0" description="还没有创新项目，点击上方'新建报门（提交创意）'开始" />
    <a-row :gutter="[16, 16]" v-else>
      <a-col v-for="p in projects" :key="p.id" :xs="24" :md="12" :lg="8">
        <a-card hoverable :title="p.title" @click="go(p)">
          <template #extra>
            <a-tag :color="STATUS_LABEL[p.status].color">{{ STATUS_LABEL[p.status].text }}</a-tag>
          </template>
          <p style="color:#888;height:60px;overflow:hidden;text-overflow:ellipsis">{{ p.description }}</p>
          <p style="color:#aaa;font-size:12px;margin-top:12px">
            {{ p.customDomain || p.domain }} · 更新 {{ new Date(p.updatedAt).toLocaleDateString() }}
          </p>
        </a-card>
      </a-col>
    </a-row>
  </a-spin>

  <NewProjectModal v-model:open="modalOpen" @created="refresh" />
</template>
