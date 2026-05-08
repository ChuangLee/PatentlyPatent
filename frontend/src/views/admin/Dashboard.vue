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
const runsTimelineRef = ref<HTMLDivElement | null>(null);
const runsFallbackRef = ref<HTMLDivElement | null>(null);

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
  loadAgentRuns(); // 不 await，监控失败不阻塞主报表
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

// v0.19-A: 一键 N 次回归
const regressionN = ref(5);
const regressionLoading = ref(false);
const regressionStats = ref<{
  total: number; ok: number; agent_error: number;
  avg_agent_chars: number; avg_mining_chars: number; avg_tool_calls: number;
  fallback_rate: number;
} | null>(null);

async function runRegression() {
  const pid = abPid.value.trim();
  if (!pid) { message.warning('请输入项目 id'); return; }
  const idea = abIdea.value.trim() || '回归测试';
  const n = Math.max(1, Math.min(20, regressionN.value || 5));
  regressionLoading.value = true;
  regressionStats.value = null;
  try {
    const results: AbCompareResp[] = [];
    for (let i = 0; i < n; i++) {
      try {
        const r = await apiClient.post<AbCompareResp>(
          `/agent/ab_compare/${pid}`,
          { idea: `${idea} (回归 ${i + 1}/${n})` },
          { timeout: 90000 },
        );
        results.push(r.data);
      } catch { /* 单次失败计入 fallback */ }
    }
    const ok = results.filter(r => !r.summary.agent_error).length;
    const fallbacks = n - ok;
    regressionStats.value = {
      total: n, ok, agent_error: fallbacks,
      avg_agent_chars: Math.round(results.reduce((s, r) => s + r.summary.agent_chars, 0) / Math.max(results.length, 1)),
      avg_mining_chars: Math.round(results.reduce((s, r) => s + r.summary.mining_chars, 0) / Math.max(results.length, 1)),
      avg_tool_calls: +(results.reduce((s, r) => s + r.summary.agent_tool_calls, 0) / Math.max(results.length, 1)).toFixed(1),
      fallback_rate: +(fallbacks / n * 100).toFixed(1),
    };
    if (fallbacks / n > 0.3) {
      message.error(`fallback 率 ${regressionStats.value.fallback_rate}% > 30% 警戒线，建议关回 PP_AGENT_PRIOR_ART`);
    } else {
      message.success(`回归 ${n} 次完成，fallback ${regressionStats.value.fallback_rate}%`);
    }
  } finally {
    regressionLoading.value = false;
  }
}

// ─── v0.20 Wave1: agent_runs admin 监控视图 ───────────────────────────────
interface AgentRunRow {
  id: number;
  endpoint: string;
  project_id: string | null;
  idea: string | null;
  num_turns: number | null;
  total_cost_usd: number | null;
  duration_ms: number;
  stop_reason: string | null;
  fallback_used: boolean;
  error: string | null;
  is_mock: boolean;
  created_at: string | null;
}

const ENDPOINT_OPTIONS = [
  { label: '全部', value: 'all' },
  { label: 'mine_spike', value: 'mine_spike' },
  { label: 'ab_compare', value: 'ab_compare' },
  { label: 'mine_full', value: 'mine_full' },
  { label: 'prior_art_smart', value: 'prior_art_smart' },
];

const runsLoading = ref(false);
const runsRaw = ref<AgentRunRow[]>([]);
const runsEndpoint = ref<string>('all');
const runsOnlyFallback = ref(false);
const runsLimit = ref(50);
const runsExpanded = ref<number[]>([]);

const runsFiltered = computed<AgentRunRow[]>(() => {
  return runsRaw.value.filter(r => {
    if (runsEndpoint.value !== 'all' && r.endpoint !== runsEndpoint.value) return false;
    if (runsOnlyFallback.value && !r.fallback_used) return false;
    return true;
  });
});

const runsColumns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 120 },
  { title: 'endpoint', dataIndex: 'endpoint', key: 'endpoint', width: 130 },
  { title: 'idea', dataIndex: 'idea', key: 'idea', ellipsis: true },
  { title: 'turns', dataIndex: 'num_turns', key: 'num_turns', width: 70 },
  { title: 'cost(USD)', dataIndex: 'total_cost_usd', key: 'total_cost_usd', width: 100 },
  { title: 'duration(ms)', dataIndex: 'duration_ms', key: 'duration_ms', width: 110 },
  { title: 'stop_reason', dataIndex: 'stop_reason', key: 'stop_reason', width: 110 },
  { title: 'fallback', dataIndex: 'fallback_used', key: 'fallback_used', width: 80 },
  { title: 'mock', dataIndex: 'is_mock', key: 'is_mock', width: 60 },
];

function relativeTime(iso: string | null): string {
  if (!iso) return '-';
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return iso;
  const diff = (Date.now() - t) / 1000;
  if (diff < 60) return `${Math.max(0, Math.floor(diff))} 秒前`;
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  return `${Math.floor(diff / 86400)} 天前`;
}

function truncate(s: string | null, n = 30): string {
  if (!s) return '-';
  return s.length > n ? s.slice(0, n) + '…' : s;
}

function fmtCost(v: number | null): string {
  if (v == null) return '-';
  return v.toFixed(4);
}

async function loadAgentRuns() {
  runsLoading.value = true;
  try {
    const r = await apiClient.get<AgentRunRow[]>('/admin/agent_runs', {
      params: { limit: Math.max(1, Math.min(500, runsLimit.value || 50)) },
    });
    runsRaw.value = Array.isArray(r.data) ? r.data : [];
    await nextTick();
    await drawRunsCharts();
  } catch (e: any) {
    message.error(`加载 agent_runs 失败：${e?.message || e}`);
  } finally {
    runsLoading.value = false;
  }
}

watch([runsFiltered], () => { drawRunsCharts(); }, { deep: true });

async function drawRunsCharts() {
  const echarts = await getEcharts();
  const rows = [...runsFiltered.value].reverse(); // oldest -> newest 时序

  // ── 1) cost over time（按 endpoint 分系列；mock 浅灰 / fallback 红，作为 markPoint）
  if (runsTimelineRef.value) {
    const inst = echarts.init(runsTimelineRef.value);
    inst.clear();
    const byEndpoint: Record<string, [string, number][]> = {};
    for (const r of rows) {
      const ep = r.endpoint || 'unknown';
      byEndpoint[ep] ??= [];
      byEndpoint[ep].push([
        r.created_at || '',
        r.total_cost_usd ?? 0,
      ]);
    }
    const PALETTE = ['#1677ff', '#16a34a', '#fa8c16', '#722ed1', '#13c2c2', '#eb2f96'];
    const series = Object.entries(byEndpoint).map(([name, data], i) => ({
      name,
      type: 'line' as const,
      smooth: true,
      data,
      itemStyle: { color: PALETTE[i % PALETTE.length] },
      markPoint: {
        symbol: 'circle',
        symbolSize: 8,
        data: rows
          .filter(r => (r.endpoint || 'unknown') === name && (r.fallback_used || r.is_mock))
          .map(r => ({
            name: r.fallback_used ? 'fallback' : 'mock',
            coord: [r.created_at || '', r.total_cost_usd ?? 0],
            itemStyle: { color: r.fallback_used ? '#cf1322' : '#bfbfbf' },
          })),
      },
    }));
    inst.setOption({
      title: { text: 'cost over time（按 endpoint 分系列）', left: 'center', textStyle: { fontSize: 13 } },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, type: 'scroll' },
      grid: { left: 50, right: 20, top: 36, bottom: 36 },
      xAxis: { type: 'time' },
      yAxis: { type: 'value', name: 'USD', axisLabel: { formatter: (v: number) => v.toFixed(4) } },
      series,
    });
  }

  // ── 2) fallback / error 率 分组柱图
  if (runsFallbackRef.value) {
    const inst = echarts.init(runsFallbackRef.value);
    inst.clear();
    const counts: Record<string, { ok: number; fallback: number; error: number }> = {};
    for (const r of runsFiltered.value) {
      const ep = r.endpoint || 'unknown';
      counts[ep] ??= { ok: 0, fallback: 0, error: 0 };
      if (r.error) counts[ep].error += 1;
      else if (r.fallback_used) counts[ep].fallback += 1;
      else counts[ep].ok += 1;
    }
    const endpoints = Object.keys(counts);
    inst.setOption({
      title: { text: '按端点统计 fallback / error 率', left: 'center', textStyle: { fontSize: 13 } },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { bottom: 0 },
      grid: { left: 50, right: 20, top: 36, bottom: 36 },
      xAxis: { type: 'category', data: endpoints },
      yAxis: { type: 'value', name: '次数' },
      series: [
        { name: 'ok', type: 'bar', stack: 'total', data: endpoints.map(e => counts[e].ok), itemStyle: { color: '#16a34a' } },
        { name: 'fallback', type: 'bar', stack: 'total', data: endpoints.map(e => counts[e].fallback), itemStyle: { color: '#fa8c16' } },
        { name: 'error', type: 'bar', stack: 'total', data: endpoints.map(e => counts[e].error), itemStyle: { color: '#cf1322' } },
      ],
    });
  }
}

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

  <!-- v0.18-D + v0.19-A: prior_art A/B 对比 + N 次回归 -->
  <a-card style="margin-top:16px" title="⚗️ prior_art A/B 对比（mining 老路径 vs agent 路径）">
    <a-space wrap>
      <a-input v-model:value="abPid" placeholder="项目 id (如 p-xxxxxxxx)" style="width:240px" />
      <a-input v-model:value="abIdea" placeholder="idea 文本" style="width:360px" />
      <a-button type="primary" :loading="abLoading" @click="runAbCompare">
        ⚗️ 单次 A/B
      </a-button>
      <a-input-number v-model:value="regressionN" :min="1" :max="20" style="width:90px" />
      <a-button :loading="regressionLoading" @click="runRegression">
        🔁 N 次回归
      </a-button>
    </a-space>
    <div style="margin-top:8px;color:#999;font-size:12px">
      单次：落盘到该项目 .ai-internal/_compare/。N 次回归：连续跑统计 fallback 率（>30% 警戒）。
    </div>
    <div v-if="regressionStats" style="margin-top:12px">
      <a-alert
        :type="regressionStats.fallback_rate > 30 ? 'error' : (regressionStats.fallback_rate > 10 ? 'warning' : 'success')"
        show-icon>
        <template #message>
          回归 {{ regressionStats.total }} 次：成功 {{ regressionStats.ok }} / fallback {{ regressionStats.agent_error }}
          ({{ regressionStats.fallback_rate }}%)
        </template>
        <template #description>
          avg agent_chars={{ regressionStats.avg_agent_chars }} ·
          mining_chars={{ regressionStats.avg_mining_chars }} ·
          tool_calls={{ regressionStats.avg_tool_calls }}
        </template>
      </a-alert>
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

  <!-- v0.20 Wave1: agent_runs 监控视图 -->
  <a-card style="margin-top:16px" title="📊 Agent Runs (最近 N 条)">
    <template #extra>
      <a-button :loading="runsLoading" @click="loadAgentRuns">🔄 刷新</a-button>
    </template>
    <a-space wrap style="margin-bottom:12px">
      <a-segmented v-model:value="runsEndpoint" :options="ENDPOINT_OPTIONS" />
      <a-checkbox v-model:checked="runsOnlyFallback">仅看 fallback</a-checkbox>
      <span style="color:#999">limit:</span>
      <a-input-number v-model:value="runsLimit" :min="1" :max="500" :step="10" style="width:100px"
                      @change="loadAgentRuns" />
      <span style="color:#999">共 {{ runsFiltered.length }} / {{ runsRaw.length }} 行</span>
    </a-space>

    <a-row :gutter="12" style="margin-bottom:12px">
      <a-col :span="12">
        <div ref="runsTimelineRef" style="height:240px"></div>
      </a-col>
      <a-col :span="12">
        <div ref="runsFallbackRef" style="height:240px"></div>
      </a-col>
    </a-row>

    <a-table
      :columns="runsColumns"
      :data-source="runsFiltered"
      :loading="runsLoading"
      :row-key="(r: AgentRunRow) => r.id"
      :pagination="{ pageSize: 20, showSizeChanger: true }"
      size="small"
      :expanded-row-keys="runsExpanded"
      @expandedRowsChange="(keys: (string | number)[]) => runsExpanded = keys.map(Number)"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'created_at'">
          <a-tooltip :title="record.created_at">{{ relativeTime(record.created_at) }}</a-tooltip>
        </template>
        <template v-else-if="column.key === 'idea'">
          {{ truncate(record.idea, 30) }}
        </template>
        <template v-else-if="column.key === 'total_cost_usd'">
          {{ fmtCost(record.total_cost_usd) }}
        </template>
        <template v-else-if="column.key === 'fallback_used'">
          <span :style="{ color: record.fallback_used ? '#cf1322' : '#16a34a' }">
            {{ record.fallback_used ? '✓' : '✗' }}
          </span>
        </template>
        <template v-else-if="column.key === 'is_mock'">
          <a-tag v-if="record.is_mock" color="default">M</a-tag>
          <a-tag v-else color="blue">真</a-tag>
        </template>
        <template v-else-if="column.key === 'endpoint'">
          <a-tag color="purple">{{ record.endpoint }}</a-tag>
        </template>
      </template>
      <template #expandedRowRender="{ record }">
        <div style="background:#fafafa;padding:8px">
          <div style="margin-bottom:6px"><b>idea：</b>{{ record.idea || '-' }}</div>
          <div v-if="record.error" style="color:#cf1322"><b>error：</b>{{ record.error }}</div>
          <div v-else style="color:#999">无 error</div>
        </div>
      </template>
    </a-table>
  </a-card>
</template>
