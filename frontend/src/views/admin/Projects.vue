<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { projectsApi } from '@/api/projects';
import type { Project, Domain, ProjectStatus } from '@/types';

const router = useRouter();
const projects = ref<Project[]>([]);
const filterDomain = ref<Domain | ''>('');
const filterStatus = ref<ProjectStatus | ''>('');

const STATUS_META: Record<ProjectStatus, string> = {
  drafting: '草稿', researching: '挖掘中', reporting: '检索完成', completed: '已完成（已导出）',
};
const DOMAIN_META: Record<Domain, string> = {
  cryptography: '密码学', infosec: '信息安全', ai: '人工智能', other: '其他',
};

const filtered = computed(() =>
  projects.value.filter(p =>
    (!filterDomain.value || p.domain === filterDomain.value) &&
    (!filterStatus.value || p.status === filterStatus.value),
  ),
);

const columns = [
  { title: '标题', dataIndex: 'title', ellipsis: true },
  { title: '员工', key: 'owner', width: 100 },
  { title: '领域', dataIndex: 'domain', width: 100, key: 'domain' },
  { title: '状态', dataIndex: 'status', width: 110, key: 'status' },
  { title: '专利性', key: 'pat', width: 110 },
  { title: '更新时间', dataIndex: 'updatedAt', width: 140, key: 'updatedAt' },
];

onMounted(async () => { projects.value = await projectsApi.list(); });

function viewProject(p: Project) {
  router.push(`/employee/projects/${p.id}/disclosure`);
}
</script>

<template>
  <a-page-header title="全量项目" sub-title="只读视角 · 用于走查与统计" />

  <a-space style="margin-bottom:16px">
    <a-select v-model:value="filterDomain" placeholder="按领域过滤" allow-clear style="width:160px">
      <a-select-option v-for="(label, key) in DOMAIN_META" :key="key" :value="key">{{ label }}</a-select-option>
    </a-select>
    <a-select v-model:value="filterStatus" placeholder="按状态过滤" allow-clear style="width:160px">
      <a-select-option v-for="(label, key) in STATUS_META" :key="key" :value="key">{{ label }}</a-select-option>
    </a-select>
  </a-space>

  <a-table :data-source="filtered" :columns="columns" row-key="id"
           :custom-row="(record: Project) => ({ onClick: () => viewProject(record), style: { cursor: 'pointer' } })">
    <template #bodyCell="{ column, record }: { column: { key: string }, record: Project }">
      <template v-if="column.key === 'owner'">u1 张工程师</template>
      <template v-else-if="column.key === 'domain'">{{ DOMAIN_META[record.domain] }}</template>
      <template v-else-if="column.key === 'status'">
        <a-tag>{{ STATUS_META[record.status] }}</a-tag>
      </template>
      <template v-else-if="column.key === 'pat'">
        <a-tag v-if="record.searchReport"
               :color="record.searchReport.patentability === 'strong' ? 'green' :
                       record.searchReport.patentability === 'moderate' ? 'gold' :
                       record.searchReport.patentability === 'weak' ? 'orange' : 'red'">
          {{ record.searchReport.patentability }}
        </a-tag>
        <span v-else style="color:#aaa">-</span>
      </template>
      <template v-else-if="column.key === 'updatedAt'">
        {{ new Date(record.updatedAt).toLocaleString('zh-CN', { hour12: false }) }}
      </template>
    </template>
  </a-table>
</template>
