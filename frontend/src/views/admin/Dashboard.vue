<script setup lang="ts">
import { onMounted, ref, computed, watch, nextTick } from 'vue';
import { projectsApi } from '@/api/projects';
import * as echarts from 'echarts';
import type { Project, ProjectStatus, Patentability } from '@/types';

const projects = ref<Project[]>([]);
const statusChartRef = ref<HTMLDivElement | null>(null);
const patChartRef = ref<HTMLDivElement | null>(null);

const STATUS_LABEL: Record<ProjectStatus, string> = {
  drafting: '草稿', researching: '挖掘中', reporting: '检索完成', completed: '已完成（已导出）',
};
const PAT_LABEL: Record<Patentability, string> = {
  strong: '很可能新颖', moderate: '边缘', weak: '存疑', not_recommended: '不建议',
};

const stats = computed(() => {
  const byStatus: Record<string, number> = {};
  const byPat: Record<string, number> = {};
  for (const p of projects.value) {
    byStatus[STATUS_LABEL[p.status]] = (byStatus[STATUS_LABEL[p.status]] ?? 0) + 1;
    const pat = p.searchReport?.patentability;
    if (pat) byPat[PAT_LABEL[pat]] = (byPat[PAT_LABEL[pat]] ?? 0) + 1;
  }
  return { byStatus, byPat };
});

onMounted(async () => {
  projects.value = await projectsApi.list();
  await nextTick();
  drawCharts();
});

watch(stats, () => drawCharts(), { deep: true });

function drawCharts() {
  if (statusChartRef.value) {
    echarts.init(statusChartRef.value).setOption({
      title: { text: '项目状态分布', left: 'center' },
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type: 'pie', radius: '60%',
        data: Object.entries(stats.value.byStatus).map(([n, v]) => ({ name: n, value: v })),
      }],
    });
  }
  if (patChartRef.value) {
    echarts.init(patChartRef.value).setOption({
      title: { text: '专利性结论分布', left: 'center' },
      tooltip: {},
      xAxis: { type: 'category', data: Object.keys(stats.value.byPat) },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: Object.values(stats.value.byPat), itemStyle: { color: '#1677ff' } }],
    });
  }
}
</script>

<template>
  <a-page-header title="管理员总览" sub-title="全公司创新挖掘活动一览" />

  <a-row :gutter="16">
    <a-col :span="12">
      <a-card>
        <div ref="statusChartRef" style="height:300px"></div>
      </a-card>
    </a-col>
    <a-col :span="12">
      <a-card>
        <div ref="patChartRef" style="height:300px"></div>
      </a-card>
    </a-col>
  </a-row>

  <a-row :gutter="16" style="margin-top:16px">
    <a-col :span="6">
      <a-card><a-statistic title="项目总数" :value="projects.length" /></a-card>
    </a-col>
    <a-col :span="6">
      <a-card>
        <a-statistic title="智慧芽配额"
                     :value="42" suffix="/ 100" :value-style="{ color: '#16a34a' }" />
      </a-card>
    </a-col>
    <a-col :span="6">
      <a-card>
        <a-statistic title="LLM tokens (今日)"
                     :value="183_240" :value-style="{ color: '#1677ff' }" />
      </a-card>
    </a-col>
    <a-col :span="6">
      <a-card>
        <a-statistic title="已完成（已导出）"
                     :value="(stats.byStatus['已完成（已导出）'] ?? 0)"
                     :value-style="{ color: '#16a34a' }" />
      </a-card>
    </a-col>
  </a-row>
</template>
