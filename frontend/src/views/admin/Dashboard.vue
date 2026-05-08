<script setup lang="ts">
import { onMounted, ref, computed, watch, nextTick } from 'vue';
import { message } from 'ant-design-vue';
import { projectsApi } from '@/api/projects';
import { apiClient } from '@/api/client';
import type { Project, ProjectStatus, Patentability } from '@/types';

let _echartsP: Promise<typeof import('echarts')> | null = null;
const getEcharts = () => (_echartsP ??= import('echarts'));

// v0.24-C: PatentlyPatent echarts 主题（token 色统一）
// 6 色循环 palette：indigo / violet / pink / emerald / amber / blue
const PP_PALETTE = ['#5B6CFF', '#8B5CF6', '#EC4899', '#10B981', '#F59E0B', '#3B82F6'];
const PP_FONT_SANS = "'Inter', 'PingFang SC', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif";
const PP_ECHARTS_THEME = {
  color: PP_PALETTE,
  textStyle: {
    fontFamily: PP_FONT_SANS,
    fontSize: 14,
    color: '#111827',
  },
  title: {
    textStyle: {
      fontFamily: PP_FONT_SANS,
      fontSize: 14,
      fontWeight: 600,
      color: '#5B6CFF',
    },
  },
  tooltip: {
    backgroundColor: '#FFFFFF',
    borderColor: '#E5E7EB',
    borderWidth: 1,
    textStyle: { color: '#111827', fontFamily: PP_FONT_SANS, fontSize: 13 },
    extraCssText: 'border-radius: 10px; box-shadow: 0 4px 6px -1px rgba(17,24,39,0.06), 0 2px 4px -2px rgba(17,24,39,0.04);',
  },
  axisLine: { lineStyle: { color: 'rgba(229,231,235,0.6)' } },
  splitLine: { lineStyle: { color: 'rgba(229,231,235,0.6)' } },
};

// 给单个 setOption 注入主题（merge 而非替换）
function withTheme<T extends Record<string, any>>(opt: T): T {
  return {
    color: PP_PALETTE,
    textStyle: PP_ECHARTS_THEME.textStyle,
    ...opt,
    title: opt.title
      ? {
          ...opt.title,
          textStyle: { ...PP_ECHARTS_THEME.title.textStyle, ...((opt.title as any).textStyle || {}) },
        }
      : undefined,
    tooltip: opt.tooltip
      ? { ...PP_ECHARTS_THEME.tooltip, ...opt.tooltip }
      : PP_ECHARTS_THEME.tooltip,
  } as T;
}

const projects = ref<Project[]>([]);
const statusChartRef = ref<HTMLDivElement | null>(null);
const patChartRef = ref<HTMLDivElement | null>(null);
const runsTimelineRef = ref<HTMLDivElement | null>(null);
const runsFallbackRef = ref<HTMLDivElement | null>(null);
// v0.21 任务 3: error 数随时间柱图 ref
const runsErrorBarRef = ref<HTMLDivElement | null>(null);

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
    echarts.init(statusChartRef.value).setOption(withTheme({
      title: { text: '项目状态分布', left: 'center' },
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, textStyle: { fontFamily: PP_FONT_SANS } },
      series: [{
        type: 'pie', radius: '60%',
        data: Object.entries(stats.value.byStatus).map(([n, v]) => ({ name: n, value: v })),
      }],
    }));
  }
  if (patChartRef.value) {
    echarts.init(patChartRef.value).setOption(withTheme({
      title: { text: '专利性结论分布', left: 'center' },
      tooltip: {},
      xAxis: {
        type: 'category',
        data: Object.keys(stats.value.byPat),
        axisLine: { lineStyle: { color: 'rgba(229,231,235,0.6)' } },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(229,231,235,0.6)' } },
      },
      series: [{ type: 'bar', data: Object.values(stats.value.byPat), itemStyle: { color: '#5B6CFF' } }],
    }));
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
    const series = Object.entries(byEndpoint).map(([name, data], i) => ({
      name,
      type: 'line' as const,
      smooth: true,
      data,
      itemStyle: { color: PP_PALETTE[i % PP_PALETTE.length] },
      lineStyle: { color: PP_PALETTE[i % PP_PALETTE.length], width: 2 },
      markPoint: {
        symbol: 'circle',
        symbolSize: 8,
        data: rows
          .filter(r => (r.endpoint || 'unknown') === name && (r.fallback_used || r.is_mock))
          .map(r => ({
            name: r.fallback_used ? 'fallback' : 'mock',
            coord: [r.created_at || '', r.total_cost_usd ?? 0],
            itemStyle: { color: r.fallback_used ? '#EF4444' : '#9CA3AF' },
          })),
      },
    }));
    inst.setOption(withTheme({
      title: { text: 'cost over time（按 endpoint 分系列）', left: 'center' },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, type: 'scroll', textStyle: { fontFamily: PP_FONT_SANS } },
      grid: { left: 50, right: 20, top: 36, bottom: 36 },
      xAxis: { type: 'time', axisLine: { lineStyle: { color: 'rgba(229,231,235,0.6)' } } },
      yAxis: {
        type: 'value', name: 'USD',
        axisLabel: { formatter: (v: number) => v.toFixed(4) },
        splitLine: { lineStyle: { color: 'rgba(229,231,235,0.6)' } },
      },
      series,
    }));
  }

  // ── v0.21 任务 3: error 数随时间柱图（最近 24 小时按小时 bucket）
  if (runsErrorBarRef.value) {
    const inst = echarts.init(runsErrorBarRef.value);
    inst.clear();
    const HOURS = 24;
    const now = Date.now();
    // bucket 起点对齐到当前小时整点
    const curHour = new Date(now);
    curHour.setMinutes(0, 0, 0);
    const startMs = curHour.getTime() - (HOURS - 1) * 3600_000;
    // 24 个 bucket：[startMs, startMs+1h), ..., [startMs+23h, startMs+24h)
    const labels: string[] = [];
    const counts: number[] = new Array(HOURS).fill(0);
    for (let i = 0; i < HOURS; i++) {
      const t = new Date(startMs + i * 3600_000);
      const hh = String(t.getHours()).padStart(2, '0');
      labels.push(`${hh}:00`);
    }
    // 注意：这里用 runsRaw（全部）而非 runsFiltered，避免被 endpoint 过滤丢失全局视图。
    for (const r of runsRaw.value) {
      if (!r.created_at) continue;
      // error count 定义：error 字段非空 OR fallback_used=true
      const isErr = !!r.error || !!r.fallback_used;
      if (!isErr) continue;
      const t = new Date(r.created_at).getTime();
      if (!Number.isFinite(t)) continue;
      const idx = Math.floor((t - startMs) / 3600_000);
      if (idx >= 0 && idx < HOURS) counts[idx] += 1;
    }
    inst.setOption(withTheme({
      title: { text: 'error / fallback 数随时间（最近 24h，按小时）', left: 'center' },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 50, right: 20, top: 36, bottom: 28 },
      xAxis: {
        type: 'category', data: labels,
        axisLabel: { fontSize: 10, fontFamily: PP_FONT_SANS },
        axisLine: { lineStyle: { color: 'rgba(229,231,235,0.6)' } },
      },
      yAxis: {
        type: 'value', name: '次数', minInterval: 1,
        splitLine: { lineStyle: { color: 'rgba(229,231,235,0.6)' } },
      },
      series: [{
        name: 'error+fallback',
        type: 'bar',
        data: counts,
        itemStyle: { color: '#EF4444', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 18,
      }],
    }));
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
    inst.setOption(withTheme({
      title: { text: '按端点统计 fallback / error 率', left: 'center' },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { bottom: 0, textStyle: { fontFamily: PP_FONT_SANS } },
      grid: { left: 50, right: 20, top: 36, bottom: 36 },
      xAxis: {
        type: 'category', data: endpoints,
        axisLine: { lineStyle: { color: 'rgba(229,231,235,0.6)' } },
      },
      yAxis: {
        type: 'value', name: '次数',
        splitLine: { lineStyle: { color: 'rgba(229,231,235,0.6)' } },
      },
      series: [
        { name: 'ok', type: 'bar', stack: 'total', data: endpoints.map(e => counts[e].ok), itemStyle: { color: '#10B981' } },
        { name: 'fallback', type: 'bar', stack: 'total', data: endpoints.map(e => counts[e].fallback), itemStyle: { color: '#F59E0B' } },
        { name: 'error', type: 'bar', stack: 'total', data: endpoints.map(e => counts[e].error), itemStyle: { color: '#EF4444' } },
      ],
    }));
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
  <div class="pp-admin-dashboard">
    <!-- 顶部欢迎 / 标题（pp-card 化） -->
    <div class="pp-card pp-admin-header">
      <a-page-header title="管理员总览" sub-title="全公司创新挖掘活动一览" :ghost="false" style="background:transparent;padding:0" />
    </div>

    <a-row :gutter="16">
      <a-col :span="12">
        <div class="pp-card pp-card-hover pp-chart-card">
          <div ref="statusChartRef" style="height:300px"></div>
        </div>
      </a-col>
      <a-col :span="12">
        <div class="pp-card pp-card-hover pp-chart-card">
          <div ref="patChartRef" style="height:300px"></div>
        </div>
      </a-col>
    </a-row>

    <a-row :gutter="16" style="margin-top:16px">
      <a-col :span="6">
        <div class="pp-card pp-card-hover pp-stat-card">
          <div class="pp-stat-card__label">项目总数</div>
          <div class="pp-stat-card__value">{{ projects.length }}</div>
        </div>
      </a-col>
      <a-col :span="6">
        <div class="pp-card pp-card-hover pp-stat-card">
          <div class="pp-stat-card__label">智慧芽配额</div>
          <div class="pp-stat-card__value">
            42<span class="pp-stat-card__suffix"> / 100</span>
          </div>
        </div>
      </a-col>
      <a-col :span="6">
        <div class="pp-card pp-card-hover pp-stat-card">
          <div class="pp-stat-card__label">LLM tokens (今日)</div>
          <div class="pp-stat-card__value">183,240</div>
        </div>
      </a-col>
      <a-col :span="6">
        <div class="pp-card pp-card-hover pp-stat-card">
          <div class="pp-stat-card__label">已完成（已导出）</div>
          <div class="pp-stat-card__value">{{ (stats.byStatus['已完成（已导出）'] ?? 0) }}</div>
        </div>
      </a-col>
    </a-row>

  <!-- v0.18-D + v0.19-A: prior_art A/B 对比 + N 次回归 -->
  <a-card class="pp-section-card" style="margin-top:16px" title="⚗️ prior_art A/B 对比（mining 老路径 vs agent 路径）">
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
  <a-card class="pp-section-card pp-runs-card" style="margin-top:16px" title="📊 Agent Runs (最近 N 条)">
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

    <!-- v0.21 任务 3: error 数随时间柱图（最近 24h，按小时 bucket） -->
    <a-row :gutter="12" style="margin-bottom:12px">
      <a-col :span="24">
        <div ref="runsErrorBarRef" style="height:240px"></div>
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
          <span :class="{
            'pp-cost-cell': true,
            'pp-cost-cell--alert': record.total_cost_usd != null && record.total_cost_usd > 1,
          }">{{ fmtCost(record.total_cost_usd) }}</span>
        </template>
        <template v-else-if="column.key === 'fallback_used'">
          <span :class="record.fallback_used ? 'pp-fb-cell pp-fb-cell--ok' : 'pp-fb-cell pp-fb-cell--err'">
            {{ record.fallback_used ? '✓' : '✗' }}
          </span>
        </template>
        <template v-else-if="column.key === 'is_mock'">
          <span v-if="record.is_mock" class="pp-mock-cell pp-mock-cell--mock">M</span>
          <span v-else class="pp-mock-cell pp-mock-cell--real">真</span>
        </template>
        <template v-else-if="column.key === 'endpoint'">
          <span class="pp-tag" :style="{ background: 'var(--pp-color-primary-soft)', color: 'var(--pp-color-primary-active)' }">
            {{ record.endpoint }}
          </span>
        </template>
      </template>
      <template #expandedRowRender="{ record }">
        <div class="pp-run-detail">
          <div style="margin-bottom:6px"><b>idea：</b>{{ record.idea || '-' }}</div>
          <div v-if="record.error" class="pp-run-detail__error"><b>error：</b>{{ record.error }}</div>
          <div v-else style="color:var(--pp-color-text-tertiary)">无 error</div>
        </div>
      </template>
    </a-table>
  </a-card>
  </div>
</template>

<style scoped>
.pp-admin-dashboard {
  padding: var(--pp-space-5);
  display: flex;
  flex-direction: column;
  gap: var(--pp-space-4);
  background: var(--pp-color-bg);
  min-height: 100%;
}

/* 顶部欢迎卡片 */
.pp-admin-header {
  padding: var(--pp-space-4) var(--pp-space-5);
  background: var(--pp-color-surface);
  border-radius: var(--pp-radius-lg);
  box-shadow: var(--pp-shadow-sm);
  border: 1px solid var(--pp-color-border-soft);
}
.pp-admin-header :deep(.ant-page-header-heading-title) {
  color: var(--pp-color-text);
  font-weight: var(--pp-font-weight-semibold);
}

/* 通用 pp-card 局部样式 (覆盖以保证 hover 等效果生效) */
.pp-admin-dashboard :deep(.pp-card),
.pp-admin-dashboard .pp-card {
  background: var(--pp-color-surface);
  border-radius: var(--pp-radius-lg);
  box-shadow: var(--pp-shadow-sm);
  border: 1px solid var(--pp-color-border-soft);
  padding: var(--pp-space-5);
}
.pp-admin-dashboard :deep(.pp-card-hover),
.pp-admin-dashboard .pp-card-hover {
  transition: transform var(--pp-transition), box-shadow var(--pp-transition);
}
.pp-admin-dashboard :deep(.pp-card-hover:hover),
.pp-admin-dashboard .pp-card-hover:hover {
  transform: translateY(-1px);
  box-shadow: var(--pp-shadow-md);
}

/* 图表卡片 */
.pp-chart-card {
  padding: var(--pp-space-4) var(--pp-space-5);
}

/* stats 4 卡 */
.pp-stat-card {
  display: flex;
  flex-direction: column;
  gap: var(--pp-space-2);
}
.pp-stat-card__label {
  font-size: var(--pp-font-size-sm);
  color: var(--pp-color-text-secondary);
  font-weight: var(--pp-font-weight-medium);
}
.pp-stat-card__value {
  font-size: 28px;
  font-weight: var(--pp-font-weight-semibold);
  color: var(--pp-color-primary);
  letter-spacing: -0.02em;
  line-height: var(--pp-line-height-tight);
}
.pp-stat-card__suffix {
  font-size: var(--pp-font-size-base);
  color: var(--pp-color-text-secondary);
  font-weight: var(--pp-font-weight-regular);
  margin-left: var(--pp-space-1);
}

/* section 卡片（A/B 对比 / agent_runs 等沿用 a-card） */
.pp-section-card {
  border-radius: var(--pp-radius-lg) !important;
  box-shadow: var(--pp-shadow-sm) !important;
  border: 1px solid var(--pp-color-border-soft) !important;
}
.pp-section-card :deep(.ant-card-head) {
  border-bottom: 1px solid var(--pp-color-border-soft);
}
.pp-section-card :deep(.ant-card-head-title) {
  font-weight: var(--pp-font-weight-semibold);
  color: var(--pp-color-text);
}

/* agent_runs 表格视觉 */
.pp-runs-card :deep(.ant-table-thead > tr > th) {
  background: var(--pp-color-bg) !important;
  font-weight: 600;
  color: var(--pp-color-text);
  border-bottom: 1px solid var(--pp-color-border) !important;
}
.pp-runs-card :deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid var(--pp-color-border-soft);
}
.pp-runs-card :deep(.ant-table-tbody > tr:hover > td),
.pp-runs-card :deep(.ant-table-tbody > tr.ant-table-row-hover > td) {
  background: var(--pp-color-primary-soft) !important;
}
.pp-runs-card :deep(.ant-table) {
  border-radius: var(--pp-radius-md);
}

/* cost 列告警 */
.pp-cost-cell { color: var(--pp-color-text); }
.pp-cost-cell--alert {
  color: var(--pp-color-danger);
  font-weight: var(--pp-font-weight-semibold);
}

/* fallback 列 ✓ / ✗ */
.pp-fb-cell {
  font-weight: var(--pp-font-weight-semibold);
  font-size: var(--pp-font-size-base);
}
.pp-fb-cell--ok { color: var(--pp-color-success); }
.pp-fb-cell--err { color: var(--pp-color-danger); }

/* mock 列 M=灰 italic / 真=primary */
.pp-mock-cell {
  display: inline-block;
  padding: 2px var(--pp-space-2);
  border-radius: var(--pp-radius-sm);
  font-size: var(--pp-font-size-xs);
  font-weight: var(--pp-font-weight-medium);
  line-height: 1.5;
}
.pp-mock-cell--mock {
  background: var(--pp-color-bg-elevated);
  color: var(--pp-color-text-secondary);
  font-style: italic;
}
.pp-mock-cell--real {
  background: var(--pp-color-primary-soft);
  color: var(--pp-color-primary);
}

/* expanded row detail */
.pp-run-detail {
  background: var(--pp-color-primary-soft);
  padding: var(--pp-space-3) var(--pp-space-4);
  border-radius: var(--pp-radius-md);
  font-family: var(--pp-font-mono);
  font-size: var(--pp-font-size-sm);
  color: var(--pp-color-text);
}
.pp-run-detail__error {
  color: var(--pp-color-danger);
  word-break: break-word;
}
</style>
