<script setup lang="ts">
import { onMounted, ref, computed, watch, nextTick } from 'vue';
import { message } from 'ant-design-vue';
import { projectsApi } from '@/api/projects';
import { apiClient } from '@/api/client';
import type { Project, ProjectStatus, Patentability } from '@/types';

let _echartsP: Promise<typeof import('echarts')> | null = null;
const getEcharts = () => (_echartsP ??= import('echarts'));

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
  await drawCharts();
});

watch(stats, () => drawCharts(), { deep: true });

async function drawCharts() {
  const echarts = await getEcharts();
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

// ─── v0.18-D: A/B 对比落盘 ────────────────────────────────────────────────
interface AbSummary {
  mining_lines: number;
  agent_lines: number;
  mining_chars: number;
  agent_chars: number;
  char_diff: number;
  agent_tool_calls: number;
  agent_error: string | null;
}
interface AbCompareResp {
  mining_file_id: string;
  agent_file_id: string;
  mining_md: string;
  agent_md: string;
  summary: AbSummary;
}

const abPid = ref('');
const abIdea = ref('');
const abLoading = ref(false);
const abModalOpen = ref(false);
const abResult = ref<AbCompareResp | null>(null);

async function runAbCompare() {
  const pid = abPid.value.trim();
  if (!pid) { message.warning('请输入项目 id'); return; }
  const idea = abIdea.value.trim() || '测试 ab';
  abLoading.value = true;
  try {
    const r = await apiClient.post<AbCompareResp>(
      `/agent/ab_compare/${pid}`, { idea }, { timeout: 60000 },
    );
    abResult.value = r.data;
    abModalOpen.value = true;
    if (r.data.summary.agent_error) {
      message.warning(`agent 路径失败：${r.data.summary.agent_error}（已落盘 mining）`);
    } else {
      message.success('A/B 对比已落盘 .ai-internal/_compare/');
    }
  } catch (e: any) {
    message.error(`A/B 对比失败：${e?.message || e}`);
  } finally {
    abLoading.value = false;
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

  <!-- v0.18-D: prior_art A/B 对比落盘工具 -->
  <a-card style="margin-top:16px" title="⚗️ prior_art A/B 对比（mining 老路径 vs agent 路径）">
    <a-space wrap>
      <a-input v-model:value="abPid" placeholder="项目 id (如 p-xxxxxxxx)" style="width:240px" />
      <a-input v-model:value="abIdea" placeholder="idea 文本" style="width:360px" />
      <a-button type="primary" :loading="abLoading" @click="runAbCompare">
        ⚗️ 跑 prior_art A/B 对比
      </a-button>
    </a-space>
    <div style="margin-top:8px;color:#999;font-size:12px">
      点击后并行落盘到该项目的 .ai-internal/_compare/ 下两个文件（hidden=True，前端文件树不展示）。
    </div>
  </a-card>

  <a-modal v-model:open="abModalOpen" title="A/B 对比结果" width="1200px" :footer="null">
    <template v-if="abResult">
      <a-descriptions size="small" :column="3" bordered style="margin-bottom:12px">
        <a-descriptions-item label="mining 行数">{{ abResult.summary.mining_lines }}</a-descriptions-item>
        <a-descriptions-item label="agent 行数">{{ abResult.summary.agent_lines }}</a-descriptions-item>
        <a-descriptions-item label="字数差 (agent − mining)">{{ abResult.summary.char_diff }}</a-descriptions-item>
        <a-descriptions-item label="mining 字数">{{ abResult.summary.mining_chars }}</a-descriptions-item>
        <a-descriptions-item label="agent 字数">{{ abResult.summary.agent_chars }}</a-descriptions-item>
        <a-descriptions-item label="agent tool 调用">{{ abResult.summary.agent_tool_calls }}</a-descriptions-item>
        <a-descriptions-item label="mining_file_id" :span="3">{{ abResult.mining_file_id }}</a-descriptions-item>
        <a-descriptions-item label="agent_file_id" :span="3">{{ abResult.agent_file_id }}</a-descriptions-item>
        <a-descriptions-item v-if="abResult.summary.agent_error" label="agent_error" :span="3">
          <span style="color:#cf1322">{{ abResult.summary.agent_error }}</span>
        </a-descriptions-item>
      </a-descriptions>

      <a-row :gutter="12">
        <a-col :span="12">
          <a-card title="mining 老路径（模板 + LLM_INJECT 占位）" size="small">
            <pre style="max-height:520px;overflow:auto;background:#fafafa;padding:8px;font-size:12px;white-space:pre-wrap">{{ abResult.mining_md }}</pre>
          </a-card>
        </a-col>
        <a-col :span="12">
          <a-card title="agent 路径（mine_section_via_agent，含 trace）" size="small">
            <pre style="max-height:520px;overflow:auto;background:#fafafa;padding:8px;font-size:12px;white-space:pre-wrap">{{ abResult.agent_md }}</pre>
          </a-card>
        </a-col>
      </a-row>
    </template>
  </a-modal>
</template>
