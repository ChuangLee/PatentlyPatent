<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { searchApi } from '@/api/search';
import { useAuthStore } from '@/stores/auth';
import PatentabilityCards from '@/components/search/PatentabilityCards.vue';
import HitsTable from '@/components/search/HitsTable.vue';
import ReadonlyBanner from '@/components/common/ReadonlyBanner.vue';
import type { Project, SearchReport } from '@/types';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const project = ref<Project | null>(null);
const report = ref<SearchReport | null>(null);
const loading = ref(true);

const isReadonly = computed(() => auth.role === 'admin');

onMounted(async () => {
  const id = route.params.id as string;
  project.value = await projectsApi.get(id);
  report.value = project.value?.searchReport
    ?? await searchApi.run(id);
  loading.value = false;
});

function next() {
  router.push(`/employee/projects/${route.params.id}/disclosure`);
}
</script>

<template>
  <ReadonlyBanner :show="isReadonly" />
  <a-page-header :title="project?.title ?? ''" sub-title="检索报告 · 4 档专利性结论 + 命中文献" />

  <a-spin :spinning="loading">
    <template v-if="report">
      <PatentabilityCards :value="report.patentability" :rationale="report.rationale" />
      <HitsTable :hits="report.hits" />
      <div style="margin-top:32px;text-align:center">
        <a-button v-if="!isReadonly" type="primary" size="large" @click="next">
          下一步：起草交底书 →
        </a-button>
      </div>
    </template>
  </a-spin>
</template>
