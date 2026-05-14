<script setup lang="ts">
import { ref, computed, watch, watchEffect, onUnmounted, nextTick } from 'vue';
import { useChatStore } from '@/stores/chat';
import { useFilesStore } from '@/stores/files';
import { useUIStore } from '@/stores/ui';
import { useAuthStore } from '@/stores/auth';
import { chatApi } from '@/api/chat';
import Button from 'ant-design-vue/es/button';
import Input from 'ant-design-vue/es/input';
import Segmented from 'ant-design-vue/es/segmented';
import Collapse from 'ant-design-vue/es/collapse';
import Spin from 'ant-design-vue/es/spin';
import { renderMarkdown, renderMermaidIn } from '@/utils/md';

const CollapsePanel = Collapse.Panel;

function fmtToolInput(v: unknown): string {
  try { return JSON.stringify(v, null, 2); } catch { return String(v); }
}

// v0.36.5: tool 名/icon/args 短展示
const TOOL_ICON_MAP: Record<string, string> = {
  search_patents: '🔍',
  search_trends: '📈',
  search_applicants: '🏢',
  inventor_ranking: '👤',
  legal_status: '⚖️',
  search_kb: '📚',
  read_kb_file: '📖',
  read_user_file: '📎',
  file_search_in_project: '🗂️',
  file_write_section: '✍️',
  save_research: '💾',
  update_plan: '📋',
};
function shortToolName(full: string): string {
  const short = String(full || '').replace(/^mcp__[^_]+__/, '');
  return short || full;
}
function toolIcon(full: string): string {
  const short = shortToolName(full);
  return TOOL_ICON_MAP[short] ?? '🔧';
}
// v0.37: 把连续的 tool_call / thinking 合并成一组"调研过程"，默认折叠
type ChatGroup =
  | { kind: 'msg'; m: any }
  | { kind: 'work'; id: string; items: any[]; running: boolean; lastTool: string };
const expandedGroups = ref<Set<string>>(new Set());
function toggleGroup(id: string) {
  const s = new Set(expandedGroups.value);
  if (s.has(id)) s.delete(id); else s.add(id);
  expandedGroups.value = s;
}

function shortToolArgs(input: unknown): string {
  if (!input || typeof input !== 'object') return '';
  const obj = input as Record<string, unknown>;
  // 优先字段：query / keyword / path / name；其余 fallback
  const preferred = ['query', 'keyword', 'path', 'name'];
  for (const k of preferred) {
    if (k in obj && obj[k]) {
      const v = String(obj[k]);
      return v.length > 80 ? v.slice(0, 80) + '…' : v;
    }
  }
  const keys = Object.keys(obj);
  if (keys.length === 0) return '';
  const first = obj[keys[0]];
  const s = typeof first === 'string' ? first : JSON.stringify(first);
  return s.length > 80 ? s.slice(0, 80) + '…' : s;
}

function fmtTs(ts: string): string {
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return ts;
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch { return ts; }
}

const props = defineProps<{ projectId: string; round: number }>();
const emit = defineEmits<{ (e: 'roundComplete', captured: string[]): void }>();

const chat = useChatStore();

// v0.37: 渲染层把连续的 tool_call/thinking 合并成 1 个"调研过程"分组
const groupedMessages = computed<ChatGroup[]>(() => {
  const out: ChatGroup[] = [];
  let workItems: any[] = [];
  const flushWork = () => {
    if (workItems.length === 0) return;
    const last = workItems[workItems.length - 1];
    const hasRunning = workItems.some(it =>
      it.type === 'tool_call' && it.tool && it.tool.result == null && (it.tool as any).status !== 'error',
    );
    const id = `g-${workItems[0].id}`;
    const lastTool = workItems.filter(it => it.type === 'tool_call').slice(-1)[0]?.tool?.name ?? '';
    out.push({ kind: 'work', id, items: [...workItems], running: hasRunning, lastTool: shortToolName(lastTool) });
    workItems = [];
  };
  for (const m of chat.messages) {
    const t = m.type ?? 'text';
    // step_done / step_failed 单独成项（不卷进工具折叠组）
    if (t === 'tool_call' || t === 'thinking') {
      workItems.push(m);
    } else {
      flushWork();
      out.push({ kind: 'msg', m });
    }
  }
  flushWork();
  return out;
});
const files = useFilesStore();
const ui = useUIStore();
const auth = useAuthStore();
const input = ref('');
const containerRef = ref<HTMLElement | null>(null);
let currentAbort: AbortController | null = null;
// v0.20 Wave1 任务 3: 防抖 ref——只在第一次 file 事件时自动开 split view
const splitAutoOpened = ref(false);
// v0.36.8: 本轮 interview 输出 [READY_FOR_WRITE] 后置标记，turn 结束时启 mineFull
const readyForWriteRequested = ref(false);

// v0.36: streaming 时每秒 tick 一次以驱动 elapsed 计时显示
const tickNow = ref(Date.now());
let tickTimer: ReturnType<typeof setInterval> | null = null;
watch(() => chat.streaming, (s) => {
  if (s && !tickTimer) {
    tickNow.value = Date.now();
    tickTimer = setInterval(() => { tickNow.value = Date.now(); }, 1000);
  } else if (!s && tickTimer) {
    clearInterval(tickTimer); tickTimer = null;
    // v0.37: streaming 结束时统一渲染 chat 里的 mermaid 图（流式中 token 不全没法渲）
    nextTick(() => { void renderMermaidIn(containerRef.value); });
  }
}, { immediate: true });
onUnmounted(() => { if (tickTimer) clearInterval(tickTimer); });

// v0.37: 历史对话恢复（attach 直接灌消息）也尝试一次渲染
watch(() => chat.messages.length, () => {
  if (!chat.streaming) nextTick(() => { void renderMermaidIn(containerRef.value); });
}, { flush: 'post' });

const elapsedSec = computed(() => {
  if (!chat.streaming || !chat.workStartedAt) return 0;
  return Math.max(0, Math.floor((tickNow.value - chat.workStartedAt) / 1000));
});

// v0.36: 卡死自愈——streaming=true 且 60s 没新 event 自动取消
const STUCK_TIMEOUT_MS = 60_000;
watchEffect(() => {
  if (!chat.streaming || !chat.lastEventAt) return;
  const sinceLast = tickNow.value - chat.lastEventAt;
  if (sinceLast > STUCK_TIMEOUT_MS) {
    console.warn('[stuck-detector] no SSE event for', sinceLast, 'ms, force reset');
    chat.appendError(`AI 长时间无响应（${Math.round(sinceLast/1000)}s 无活动），已自动取消，请重试。`);
    chat.endAgent();
    if (currentAbort) { currentAbort.abort(); currentAbort = null; }
  }
});

function cancelStream() {
  if (currentAbort) {
    currentAbort.abort();
    currentAbort = null;
    chat.endAgent();
  }
  // v0.34: 还要把后端 task 也取消，否则它继续跑下去
  const rid = chat.currentRunId;
  if (rid) {
    chatApi.agentRuns.cancel(rid).catch((e) => {
      console.warn('[cancel run] failed', e?.message || e);
    });
    chat.setCurrentRun(null);
  }
}

/** v0.34: 公共事件 handler — 用于 SSE stream / 历史 events 重放共享。 */
function applyAgentEvent(e: any) {
  // 透传后端 detached run 的 seq → store
  if (typeof e?.__seq === 'number') chat.bumpLastSeq(e.__seq);
  // v0.36: 任意事件刷活动时间，喂给卡死自愈 watcher
  chat.bumpActivity();

  if (e.type === 'delta') {
    // 兼容 chunk / text 两种字段
    const txt: string = typeof e.chunk === 'string' ? e.chunk : (typeof e.text === 'string' ? e.text : '');
    if (txt) {
      // 第一个 delta 到达时清掉 phase（让 status bar 切到"输出中"）
      if (chat.latestPhase && chat.latestPhase !== '正在输出回答…') {
        chat.setLatestPhase('正在输出回答…');
      }
      // v0.36: interview agent 在末尾加信号；前端捕获并自动跳转下一阶段
      let cleaned = txt;
      if (cleaned.includes('[READY_FOR_WRITE]')) {
        // 阶段 ① → ②：用户问完了，自动启 mineFull 写 5 节
        chat.setLatestPhase('挖掘完成，准备写章节…');
        readyForWriteRequested.value = true;
        cleaned = cleaned.replace(/\[READY_FOR_WRITE\]/g, '').trim();
      }
      if (cleaned.includes('[READY_FOR_DOCX]')) {
        chat.setReadyForDocx(true);
        cleaned = cleaned.replace(/\[READY_FOR_DOCX\]/g, '').trim();
      }
      if (cleaned) chat.appendDelta(cleaned);
    }
  } else if (e.type === 'thinking' && e.text) {
    chat.appendThinking(e.text);
    chat.setLatestPhase(e.text);
  } else if (e.type === 'tool_use') {
    // v0.36.5: update_plan 工具是"虚拟"的，不渲染为普通工具卡片，而是更新顶部 Plan
    const toolName = (e.name || '').toString();
    const isPlanTool = toolName.endsWith('__update_plan') || toolName === 'update_plan';
    if (isPlanTool) {
      try {
        const raw = (e.input || {}).steps_json;
        const steps = typeof raw === 'string' ? JSON.parse(raw) : (Array.isArray(raw) ? raw : []);
        if (Array.isArray(steps)) chat.setPlan(steps);
        chat.setLatestPhase('更新计划清单…');
      } catch (err) {
        console.warn('[update_plan parse]', err);
      }
    } else {
      chat.appendToolCall(toolName, e.input, e.id);
      // 短名展示（去 mcp__patent-tools__ 前缀）
      const short = toolName.replace(/^mcp__[^_]+__/, '');
      chat.setLatestPhase(`调用工具 ${short}…`);
    }
  } else if (e.type === 'tool_result') {
    chat.attachToolResult(e.text, e.data, e.tool_use_id);
    chat.setLatestPhase('收到工具结果，继续推理…');
  }
  else if (e.type === 'error') chat.appendError(e.message || 'unknown error');
  else if (e.type === 'file' && e.node) {
    const existing = files.tree.find(n => n.id === e.node.id);
    if (existing) Object.assign(existing, e.node);
    else files.pushNode(e.node);
    files.selectFile(e.node.id);
    files.markSpawnedNode(e.node.id);
    autoOpenSplitOnFirstFile();
  } else if (e.type === 'section_start' && (e.name || e.section)) {
    chat.setSectionStatus(e.name || e.section, 'running');
  } else if (e.type === 'section_done' && (e.name || e.section)) {
    chat.setSectionStatus(e.name || e.section, 'done');
  } else if (e.type === 'done') {
    // v0.37: 如果这轮 stop_reason=tool_use 表示用满 turn 没产 text → 自动提示
    if (e.stop_reason === 'tool_use') {
      chat.appendError('代理人这轮工具调用用满预算未给结论。请在下方输入"继续"让 AI 收尾。');
    }
    chat.endAgent();
  } else if (e.type === 'stream_end') {
    chat.endAgent();
  }
}

/**
 * v0.34: 走 detached run — 客户端断开后台仍跑。
 * 1) start 拿 run_id，存 store
 * 2) SSE tail since=0
 * v0.36: mineFull 终态后自动续跑 interview 首轮
 */
async function startDetachedRun(
  endpoint: 'mine_spike' | 'mine_full',
  idea: string,
  projectId?: string,
) {
  chat.resetSectionProgress();
  chat.setInterviewActive(false);
  chat.setReadyForDocx(false);
  chat.startAgent();
  let runId: string;
  try {
    const r = await chatApi.agentRuns.start({ endpoint, project_id: projectId, idea });
    runId = r.run_id;
    chat.setCurrentRun(runId);
  } catch (err) {
    chat.appendError('启动失败：' + (err as Error).message);
    chat.endAgent();
    throw err;
  }

  currentAbort = new AbortController();
  let runStatus: string | null = null;
  try {
    await chatApi.agentRuns.stream(runId, 0, applyAgentEvent, currentAbort.signal);
  } finally {
    currentAbort = null;
    // SSE 自然结束（stream_end）或被 abort 时清掉 currentRunId（终态）
    try {
      const info = await chatApi.agentRuns.get(runId);
      runStatus = info.status;
      if (info.status !== 'running') chat.setCurrentRun(null);
    } catch { /* ignore */ }
  }

  // v0.36: mineFull 跑完且无错误 → 进 interview 阶段，AI 主动追问首轮
  if (endpoint === 'mine_full' && runStatus === 'completed' && projectId) {
    await startInterviewTurn(projectId, undefined);
  }
}

/** v0.36: 启动一轮 interview（首轮 user_msg=undefined；后续轮带 user_msg） */
async function startInterviewTurn(projectId: string, userMsg?: string) {
  chat.setInterviewActive(true);
  chat.clearPlan();   // v0.36.5: 新轮清旧 plan
  readyForWriteRequested.value = false;   // v0.36.8: 本轮重置 ready_for_write 标记
  chat.startAgent();
  // 首轮前推个引导提示，让用户看到状态变化
  if (!userMsg) chat.appendThinking('🧑‍⚖️ 我是您的专利代理人，我先消化一下您的资料…');

  // 拼 history：取所有 text 类气泡（过滤 thinking/tool 卡片）
  const history = chat.messages
    .filter(m => (m.type ?? 'text') === 'text' && m.content && m.content.trim())
    .map(m => ({ role: m.role, content: m.content }));

  currentAbort = new AbortController();
  try {
    await chatApi.interviewStream(
      projectId,
      { user_msg: userMsg, history },
      applyAgentEvent,
      currentAbort.signal,
    );
  } catch (err) {
    chat.appendError('interview 失败：' + (err as Error).message);
  } finally {
    currentAbort = null;
    chat.endAgent();
  }

  // v0.36.8: 代理人宣告 ready 后自动跑 mineFull 写 5 节，然后再起一轮收尾 interview
  if (readyForWriteRequested.value) {
    readyForWriteRequested.value = false;
    chat.appendThinking('✍️ 信息已经够清晰了，我开始写 5 节交底书初稿…');
    try {
      await startDetachedRun('mine_full', userMsg || chat.messages.filter(m => m.role === 'user').slice(-1)[0]?.content || '（无描述）', projectId);
    } catch (err) {
      chat.appendError('写章节失败：' + (err as Error).message);
    }
  }
}

/**
 * v0.34: 重连恢复 — 给定 run_id，先拉 [since..] 历史 events 渲染，再 SSE tail。
 */
async function resumeRun(runId: string, since: number) {
  chat.setCurrentRun(runId);
  chat.startAgent();
  try {
    // 拉历史 events 一次性渲染（不等服务端推）
    const evs = await chatApi.agentRuns.events(runId, since);
    for (const row of evs) {
      const payload = { ...(row.payload || {}), type: row.type, __seq: row.seq } as any;
      applyAgentEvent(payload);
    }
    // 若 run 还在跑，SSE tail
    const info = await chatApi.agentRuns.get(runId);
    if (info.status === 'running') {
      currentAbort = new AbortController();
      try {
        await chatApi.agentRuns.stream(runId, chat.lastEventSeq, applyAgentEvent, currentAbort.signal);
      } finally {
        currentAbort = null;
      }
      const final = await chatApi.agentRuns.get(runId);
      if (final.status !== 'running') chat.setCurrentRun(null);
    } else {
      chat.endAgent();
      chat.setCurrentRun(null);
    }
  } catch (err) {
    console.warn('[resumeRun]', err);
    chat.appendError('恢复失败：' + (err as Error).message);
    chat.endAgent();
  }
}

/**
 * v0.20 Wave1 任务 3: 收到第一条 file 事件且 split view 关着时自动开。
 * 用 splitAutoOpened ref 防抖，整个组件生命周期只触发一次。
 */
function autoOpenSplitOnFirstFile() {
  if (splitAutoOpened.value) return;
  splitAutoOpened.value = true;
  if (!ui.workbenchSplitView) {
    ui.toggleWorkbenchSplitView();
  }
}

watch(() => chat.messages.length, () => {
  nextTick(() => {
    if (containerRef.value) containerRef.value.scrollTop = containerRef.value.scrollHeight;
  });
}, { flush: 'post' });

async function send() {
  const text = input.value.trim();
  if (!text || chat.streaming) return;
  chat.appendUser(text);
  input.value = '';

  // v0.36.2: 默认全部走 interview 端点（资深代理人 + 8 个智慧芽工具）
  // 这样 chat 里能看到 AI 的整个工作过程：thinking 卡片 + 工具调用卡片 + 中间 delta
  // 老 chat 端点（无工具）仅在 mining 模式 admin 调试时用
  if (ui.agentMode === 'agent_sdk') {
    await startInterviewTurn(props.projectId, text);
    return;
  }

  // 老路径：mining 模式（admin 切换后才走）
  chat.startAgent();
  currentAbort = new AbortController();
  try {
    await chatApi.stream(props.projectId, props.round, text, e => {
      if (e.type === 'delta') chat.appendDelta(e.chunk);
      else if (e.type === 'fields') {
        chat.applyFields(e.captured);
        emit('roundComplete', e.captured);
      } else if (e.type === 'file') {
        // AI 在文件树上 spawn / 更新文件 → 同时自动选中让右栏预览
        const existing = files.tree.find(n => n.id === e.node.id);
        if (existing) {
          // 已存在节点更新（用户答写回时 fileNode.content 改了）
          Object.assign(existing, e.node);
        } else {
          files.pushNode(e.node);
        }
        files.selectFile(e.node.id);
        files.markSpawnedNode(e.node.id);  // v0.21 任务 4: 通知 FileTree 滚动到该节点
        autoOpenSplitOnFirstFile();
      } else if (e.type === 'done') {
        chat.endAgent();
      }
    }, currentAbort.signal);
  } finally {
    currentAbort = null;
  }
}

/** 由父组件（ProjectWorkbench）调，进入工作台时自动跑挖掘流程 */
async function autoMine(ctx: Parameters<typeof chatApi.autoMine>[1]) {
  // v0.34.4: 进 autoMine 时如果上一轮 streaming 卡 true（无活动 SSE），强制重置
  if (chat.streaming && !currentAbort) {
    console.warn('[autoMine] streaming stuck without active abort, reset');
    chat.endAgent();
  }
  if (chat.streaming) return;
  const useAgentSdk = ui.agentMode === 'agent_sdk';
  if (useAgentSdk) {
    const idea = [ctx.title, ctx.description, ctx.intake?.notes].filter(Boolean).join('\n');
    try {
      await startDetachedRun('mine_full', idea || '（无描述）', props.projectId);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const { default: antMessage } = await import('ant-design-vue/es/message');
      antMessage.error(`mine_full 失败：${msg}`);
    }
    return;
  }
  // 老 mining 路径走旧 SSE（不持久化；按用户原话只是前端显示）
  chat.resetSectionProgress();
  chat.startAgent();
  currentAbort = new AbortController();
  try {
    await chatApi.autoMine(props.projectId, ctx, applyAgentEvent, currentAbort.signal);
  } finally {
    currentAbort = null;
  }
}

/** v0.21 任务 1: 一键全程挖掘 — agent_sdk 模式专用，由父组件按钮触发 */
async function mineFull(idea: string) {
  if (chat.streaming && !currentAbort) {
    console.warn('[mineFull] streaming stuck, reset');
    chat.endAgent();
  }
  if (chat.streaming) return;
  try {
    await startDetachedRun('mine_full', idea || '（无描述）', props.projectId);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const { default: antMessage } = await import('ant-design-vue/es/message');
    antMessage.error(`一键挖掘失败：${msg}`);
    throw err;
  }
}

/** v0.36.8: 进工作台 / 重启 interview-first 流程的入口 */
async function startFirstInterview() {
  if (chat.streaming) return;
  await startInterviewTurn(props.projectId, undefined);
}

/** 断点续作：调 /interview/{pid}/resume，后端拼好 history+plan 摘要拼 prompt 头 */
async function resumeFromSnapshot() {
  if (chat.streaming) return;
  chat.setInterviewActive(true);
  chat.startAgent();
  chat.appendThinking('📂 续作中：从上次中断的工作步骤继续…');
  currentAbort = new AbortController();
  try {
    await chatApi.interviewResumeStream(
      props.projectId,
      applyAgentEvent,
      currentAbort.signal,
    );
  } catch (err) {
    chat.appendError('续作失败：' + (err as Error).message);
  } finally {
    currentAbort = null;
    chat.endAgent();
  }
  if (readyForWriteRequested.value) {
    readyForWriteRequested.value = false;
    chat.appendThinking('✍️ 信息已经够清晰了，我开始写 5 节交底书初稿…');
    try {
      const lastUser = chat.messages.filter(m => m.role === 'user').slice(-1)[0]?.content || '（无描述）';
      await startDetachedRun('mine_full', lastUser, props.projectId);
    } catch (err) {
      chat.appendError('写章节失败：' + (err as Error).message);
    }
  }
}

defineExpose({ autoMine, mineFull, resumeRun, startFirstInterview, resumeFromSnapshot });
</script>

<template>
  <div class="pp-chat-root">
    <!-- v0.36.5: Plan/TODO 卡片 sticky 在 chat 顶部，agent 当前轮工作计划 -->
    <div v-if="chat.currentPlan && chat.currentPlan.length > 0" class="pp-plan-card">
      <div class="pp-plan-head">
        <span class="pp-plan-title">📋 当前计划</span>
        <span class="pp-plan-progress">
          已完成 {{ chat.currentPlan.filter(s => s.status === 'completed').length }} /
          {{ chat.currentPlan.length }}
        </span>
      </div>
      <ul class="pp-plan-list">
        <li v-for="step in chat.currentPlan" :key="step.id"
            class="pp-plan-step"
            :class="`pp-plan-step-${step.status}`">
          <span class="pp-plan-icon">
            <template v-if="step.status === 'completed'">✓</template>
            <template v-else-if="step.status === 'in_progress'">⏳</template>
            <template v-else-if="step.status === 'failed'">✗</template>
            <template v-else>○</template>
          </span>
          <span class="pp-plan-step-title">{{ step.title }}</span>
          <span v-if="step.note" class="pp-plan-note">— {{ step.note }}</span>
        </li>
      </ul>
    </div>

    <div ref="containerRef" class="pp-chat-stream">
      <div v-if="chat.messages.length === 0" class="pp-chat-empty">
        尚未开始对话——发送第一条消息让 AI 开始引导。
      </div>
      <template v-for="g in groupedMessages" :key="g.kind === 'msg' ? g.m.id : g.id">
        <!-- 1) 调研过程分组（连续的 thinking + tool_call 合并为可折叠卡） -->
        <div v-if="g.kind === 'work'" class="pp-chat-row pp-chat-row-agent">
          <div class="pp-work-group">
            <div class="pp-work-head" @click="toggleGroup(g.id)">
              <span class="pp-work-icon">{{ g.running ? '⏳' : '✓' }}</span>
              <span class="pp-work-title">
                {{ g.running ? `调研中…${g.lastTool ? `（${g.lastTool}）` : ''}` : `调研过程 · ${g.items.length} 步` }}
              </span>
              <span class="pp-work-toggle">{{ expandedGroups.has(g.id) ? '收起 ▲' : '展开 ▼' }}</span>
            </div>
            <div v-if="expandedGroups.has(g.id)" class="pp-work-body">
              <template v-for="it in g.items" :key="it.id">
                <div v-if="it.type === 'thinking'" class="pp-work-item pp-work-thinking">
                  💭 {{ it.content }}
                </div>
                <div v-else-if="it.type === 'tool_call' && it.tool" class="pp-work-item">
                  <div class="pp-tool-head">
                    <span class="pp-tool-icon">{{ toolIcon(it.tool.name) }}</span>
                    <span class="pp-tool-name">{{ shortToolName(it.tool.name) }}</span>
                    <span class="pp-tool-args-inline">{{ shortToolArgs(it.tool.input) }}</span>
                    <span v-if="(it.tool as any).status === 'error'" class="pp-tool-badge pp-tool-badge-danger">✗</span>
                    <span v-else-if="it.tool.result == null" class="pp-tool-badge pp-tool-badge-running"><Spin size="small" /></span>
                    <span v-else class="pp-tool-badge pp-tool-badge-success">✓</span>
                    <span v-if="it.tool.tDurationMs != null" class="pp-tool-time">{{ it.tool.tDurationMs }}ms</span>
                  </div>
                  <Collapse v-if="it.tool.result != null || (it.tool as any).status === 'error'"
                            :bordered="false" ghost size="small" class="pp-tool-collapse">
                    <CollapsePanel key="result"
                                   :header="(it.tool as any).status === 'error' ? '查看错误' : '查看结果'">
                      <pre class="pp-tool-pre">{{ it.tool.result }}</pre>
                    </CollapsePanel>
                  </Collapse>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- 2) 普通对话气泡（user / agent text） -->
        <template v-else-if="g.kind === 'msg'">
          <div v-if="(g.m.type ?? 'text') === 'text'"
               class="pp-chat-row"
               :class="g.m.role === 'user' ? 'pp-chat-row-user' : 'pp-chat-row-agent'">
            <div v-if="g.m.role !== 'user'" class="pp-chat-avatar" aria-hidden="true">AI</div>
            <div class="pp-chat-bubble-wrap">
              <div class="pp-chat-bubble"
                   :class="g.m.role === 'user' ? 'pp-chat-bubble-user' : 'pp-chat-bubble-agent'">
                <div v-if="g.m.role === 'agent'" class="pp-chat-md" v-html="renderMarkdown(g.m.content)"></div>
                <span v-else>{{ g.m.content }}</span>
                <span v-if="g.m.role === 'agent' && chat.streaming
                            && g.m.id === chat.messages[chat.messages.length-1].id"
                      class="pp-chat-cursor">|</span>
              </div>
              <div v-if="g.m.ts" class="pp-chat-timestamp"
                   :class="{ 'pp-chat-timestamp-right': g.m.role === 'user' }">
                {{ fmtTs(g.m.ts) }}
              </div>
            </div>
          </div>
          <!-- v0.37 harness: plan step 完成/失败汇报（独立单行不折叠） -->
          <div v-else-if="g.m.type === 'step_done'" class="pp-chat-row pp-chat-row-agent">
            <div class="pp-step-done">{{ g.m.content }}</div>
          </div>
          <div v-else-if="g.m.type === 'step_failed'" class="pp-chat-row pp-chat-row-agent">
            <div class="pp-step-failed">{{ g.m.content }}</div>
          </div>
          <!-- error 卡片 -->
          <div v-else-if="g.m.type === 'error'" class="pp-chat-row pp-chat-row-agent">
            <div class="pp-chat-error">❌ {{ g.m.content }}</div>
          </div>
        </template>
      </template>
    </div>

    <!-- v0.36: 常驻状态条——streaming 时显示 phase + elapsed timer + 取消 -->
    <div v-if="chat.streaming" class="pp-chat-status">
      <div class="pp-chat-status-spinner" aria-hidden="true">
        <span class="pp-dot"></span>
        <span class="pp-dot"></span>
        <span class="pp-dot"></span>
      </div>
      <div class="pp-chat-status-text">
        <span class="pp-chat-status-phase">{{ chat.latestPhase || 'AI 思考中' }}</span>
        <span class="pp-chat-status-elapsed">{{ elapsedSec }}s</span>
      </div>
      <Button size="small" type="text" danger @click="cancelStream">取消</Button>
    </div>

    <div class="pp-chat-composer">
      <!-- v0.37: mining 模式弃用，模式切换器移除 -->
      <div class="pp-chat-input-row">
        <Input v-model:value="input" placeholder="描述你的发明，或回答 AI 的问题..."
               :disabled="chat.streaming" @press-enter="send" />
        <Button type="primary" :loading="chat.streaming" @click="send">发送</Button>
        <Button v-if="chat.streaming" danger @click="cancelStream">🛑 取消</Button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ---------- 容器 ---------- */
.pp-chat-root {
  display: flex;
  flex-direction: column;
  height: 100%;
  font-family: var(--pp-font-sans);
}
.pp-chat-stream {
  flex: 1;
  overflow-y: auto;
  padding: var(--pp-space-4);
  background: var(--pp-color-bg);
}
.pp-chat-empty {
  color: var(--pp-color-text-tertiary);
  text-align: center;
  padding-top: 80px;
  font-size: var(--pp-font-size-sm);
}

/* ---------- 行容器（含 avatar + bubble） ---------- */
.pp-chat-row {
  display: flex;
  align-items: flex-start;
  gap: var(--pp-space-2);
  margin-bottom: 10px;       /* v0.37: 24→10px */
}
.pp-chat-row-user { justify-content: flex-end; }
.pp-chat-row-agent {
  justify-content: flex-start;
}
/* v0.37: agent 行的 bubble-wrap 铺满剩余宽（避免右侧大片空白） */
.pp-chat-row-agent .pp-chat-bubble-wrap { flex: 1 1 auto; max-width: none; }

/* ---------- agent avatar（v0.37: 缩到 20px 不占地） ---------- */
.pp-chat-avatar {
  flex: none;
  width: 20px;
  height: 20px;
  border-radius: var(--pp-radius-full);
  background: linear-gradient(135deg, var(--pp-color-primary) 0%, #8B5CF6 50%, #EC4899 100%);
  color: #fff;
  font-size: 9px;
  font-weight: var(--pp-font-weight-bold);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0.5px;
  margin-top: 1px;
}

/* ---------- bubble wrapper（含 timestamp） ---------- */
.pp-chat-bubble-wrap {
  display: flex;
  flex-direction: column;
  max-width: 70%;
  min-width: 0;
}

/* ---------- bubble 主体 ---------- */
.pp-chat-bubble {
  position: relative;
  padding: 6px 12px;          /* v0.37: 10→6px */
  border-radius: var(--pp-radius-lg);
  /* v0.37: 删 white-space:pre-wrap，否则 markdown 渲染后 \n 又被显示成换行（叠加 <p> 标签变双倍空白） */
  word-break: break-word;
  font-size: var(--pp-font-size-base);
  line-height: 1.45;
}
/* user 气泡仍然要保留原始换行（用户输入纯文本） */
.pp-chat-bubble-user { white-space: pre-wrap; }

/* user 气泡：渐变 indigo→violet + 白字 + 右下小三角 */
.pp-chat-bubble-user {
  background: linear-gradient(135deg, var(--pp-color-primary) 0%, #8B5CF6 100%);
  color: var(--pp-color-text-inverse);
  box-shadow: var(--pp-shadow-sm);
}
.pp-chat-bubble-user::after {
  content: '';
  position: absolute;
  right: -6px;
  bottom: 8px;
  width: 0;
  height: 0;
  border-style: solid;
  border-width: 6px 0 6px 8px;
  border-color: transparent transparent transparent #8B5CF6;
}

/* agent 气泡：白底 + soft border */
.pp-chat-bubble-agent {
  background: var(--pp-color-surface);
  color: var(--pp-color-text);
  border: 1px solid var(--pp-color-border-soft);
  box-shadow: var(--pp-shadow-sm);
}

/* v0.36 markdown 渲染样式：表格 / 代码 / 列表 / 标题 */
/* v0.37: 用 :deep() 穿透 scoped CSS，否则 v-html 注入的元素不带 data-v 属性匹配不到 */
.pp-chat-md { line-height: 1.45; word-break: break-word; }
.pp-chat-md :deep(> :first-child) { margin-top: 0; }
.pp-chat-md :deep(> :last-child) { margin-bottom: 0; }
.pp-chat-md :deep(p) { margin: 4px 0; }
.pp-chat-md :deep(br) { display: none; }
.pp-chat-md :deep(.pp-mermaid) {
  margin: 10px 0;
  padding: 10px;
  background: #fafafa;
  border: 1px solid var(--pp-color-border-soft);
  border-radius: 6px;
  text-align: center;
  overflow-x: auto;
}
.pp-chat-md :deep(.pp-mermaid svg) { max-width: 100%; height: auto; }
.pp-chat-md :deep(h1),
.pp-chat-md :deep(h2),
.pp-chat-md :deep(h3),
.pp-chat-md :deep(h4),
.pp-chat-md :deep(h5),
.pp-chat-md :deep(h6) {
  margin: 8px 0 2px;
  font-weight: var(--pp-font-weight-semibold);
  line-height: 1.3;
}
.pp-chat-md :deep(h1) { font-size: 1.4em; border-bottom: 1px solid var(--pp-color-border-soft); padding-bottom: 4px; }
.pp-chat-md :deep(h2) { font-size: 1.25em; }
.pp-chat-md :deep(h3) { font-size: 1.1em; }
.pp-chat-md :deep(h4) { font-size: 1em; color: var(--pp-color-text-secondary); }
.pp-chat-md :deep(ul),
.pp-chat-md :deep(ol) { margin: 4px 0; padding-left: 20px; }
.pp-chat-md :deep(li) { margin: 0; padding: 1px 0; }
.pp-chat-md :deep(li > p) { margin: 0; }
.pp-chat-md :deep(hr) {
  border: none;
  border-top: 1px solid var(--pp-color-border-soft);
  margin: 8px 0;
}
.pp-chat-md :deep(a) { color: var(--pp-color-primary); text-decoration: underline; }
.pp-chat-md :deep(strong) { font-weight: var(--pp-font-weight-semibold); color: var(--pp-color-text); }
.pp-chat-md :deep(em) { font-style: italic; }
.pp-chat-md :deep(blockquote) {
  margin: 6px 0;
  padding: 4px 10px;
  border-left: 3px solid var(--pp-color-primary);
  background: rgba(91, 108, 255, 0.06);
  color: var(--pp-color-text-secondary);
  border-radius: 0 6px 6px 0;
}
.pp-chat-md :deep(code) {
  background: rgba(0, 0, 0, 0.05);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: var(--pp-font-mono, ui-monospace, "SF Mono", Menlo, Consolas, monospace);
  font-size: 0.92em;
  color: #d63384;
}
.pp-chat-md :deep(pre) {
  margin: 6px 0;
  padding: 8px 12px;
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 0.88em;
  line-height: 1.4;
}
.pp-chat-md :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
  font-size: inherit;
}
.pp-chat-md :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 6px 0;
  font-size: 0.95em;
}
.pp-chat-md :deep(th),
.pp-chat-md :deep(td) {
  border: 1px solid var(--pp-color-border-soft);
  padding: 4px 8px;
  text-align: left;
  vertical-align: top;
}
.pp-chat-md :deep(th) {
  background: rgba(91, 108, 255, 0.08);
  font-weight: var(--pp-font-weight-semibold);
}
.pp-chat-md :deep(tr:nth-child(2n) td) { background: rgba(0, 0, 0, 0.02); }
.pp-chat-md :deep(img) { max-width: 100%; border-radius: 6px; }

/* streaming 闪烁光标 1s 循环 */
.pp-chat-cursor {
  display: inline-block;
  margin-left: 2px;
  animation: pp-chat-cursor-blink 1s ease-in-out infinite;
  color: currentColor;
  font-weight: var(--pp-font-weight-bold);
}
@keyframes pp-chat-cursor-blink {
  0%, 100% { opacity: 0.4; }
  50%      { opacity: 0.8; }
}

/* timestamp：浅灰 11px */
.pp-chat-timestamp {
  margin-top: 4px;
  font-size: 11px;
  color: var(--pp-color-text-tertiary);
  font-variant-numeric: tabular-nums;
}
.pp-chat-timestamp-right { text-align: right; }

/* ---------- tool_call 卡片 ---------- */
/* v0.36.5: Plan/TODO 卡片 —— sticky 在 chat 顶部 */
.pp-plan-card {
  margin: 0 0 8px 0;
  padding: 6px 12px;
  background: linear-gradient(135deg, rgba(91,108,255,0.06), rgba(91,108,255,0.02));
  border: 1px solid rgba(91, 108, 255, 0.2);
  border-radius: var(--pp-radius-md);
}
.pp-plan-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.pp-plan-title {
  font-weight: var(--pp-font-weight-semibold);
  font-size: 12px;
  color: var(--pp-color-primary);
}
.pp-plan-progress {
  font-size: 11px;
  color: var(--pp-color-text-secondary);
  font-variant-numeric: tabular-nums;
}
.pp-plan-list {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 12px;
}
.pp-plan-step {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 1px 0;
  color: var(--pp-color-text);
  line-height: 1.4;
}
.pp-plan-icon {
  width: 18px;
  display: inline-flex;
  justify-content: center;
  font-weight: var(--pp-font-weight-bold);
}
.pp-plan-step-title {
  flex: 1;
}
.pp-plan-note {
  color: var(--pp-color-text-tertiary);
  font-size: 12px;
}
.pp-plan-step-completed .pp-plan-icon { color: var(--pp-color-success); }
.pp-plan-step-completed .pp-plan-step-title { text-decoration: line-through; color: var(--pp-color-text-tertiary); }
.pp-plan-step-in_progress .pp-plan-icon { color: var(--pp-color-primary); animation: pp-plan-spin 1.4s linear infinite; }
.pp-plan-step-in_progress .pp-plan-step-title { color: var(--pp-color-primary); font-weight: var(--pp-font-weight-medium); }
.pp-plan-step-failed .pp-plan-icon { color: var(--pp-color-danger); }
.pp-plan-step-failed .pp-plan-step-title { color: var(--pp-color-danger); text-decoration: line-through; }
.pp-plan-step-pending .pp-plan-icon { color: var(--pp-color-text-tertiary); }
.pp-plan-step-pending .pp-plan-step-title { color: var(--pp-color-text-tertiary); }
@keyframes pp-plan-spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

/* v0.37 harness: plan step 完成/失败汇报 —— 单行轻量气泡 */
.pp-step-done {
  font-size: 12px;
  color: var(--pp-color-success, #16a34a);
  padding: 2px 10px;
  border-left: 2px solid var(--pp-color-success, #16a34a);
  background: rgba(16, 163, 74, 0.06);
  border-radius: var(--pp-radius-sm);
  width: 100%;
}
.pp-step-failed {
  font-size: 12px;
  color: var(--pp-color-danger, #dc2626);
  padding: 2px 10px;
  border-left: 2px solid var(--pp-color-danger, #dc2626);
  background: rgba(220, 38, 38, 0.06);
  border-radius: var(--pp-radius-sm);
  width: 100%;
}

/* v0.37: "调研过程"分组卡 —— 默认折叠 */
.pp-work-group {
  width: 100%;
  background: rgba(91, 108, 255, 0.04);
  border: 1px solid rgba(91, 108, 255, 0.15);
  border-radius: var(--pp-radius-md);
  overflow: hidden;
}
.pp-work-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  cursor: pointer;
  user-select: none;
  font-size: 12px;
}
.pp-work-head:hover { background: rgba(91, 108, 255, 0.06); }
.pp-work-icon { font-size: 14px; }
.pp-work-title { flex: 1; color: var(--pp-color-text-secondary); }
.pp-work-toggle { color: var(--pp-color-text-tertiary); font-size: 11px; }
.pp-work-body {
  padding: 4px 10px 6px;
  border-top: 1px dashed rgba(91, 108, 255, 0.15);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.pp-work-item {
  font-size: 11px;
  padding: 3px 0;
}
.pp-work-thinking {
  color: var(--pp-color-text-secondary);
  font-style: italic;
}

.pp-tool-card {
  /* v0.37: 铺满宽度、紧凑 padding */
  width: 100%;
  background: linear-gradient(135deg, #EEF0FF 0%, #FCE7F3 100%);
  border: 1px solid rgba(91, 108, 255, 0.2);
  border-radius: var(--pp-radius-md);
  padding: 4px 10px;
  font-size: var(--pp-font-size-xs);
  box-shadow: none;
}
.pp-tool-head { margin-bottom: 0 !important; }
.pp-tool-collapse :deep(.ant-collapse-header) {
  padding: 2px 0 !important;
  font-size: 11px;
}
.pp-tool-card-err {
  background: linear-gradient(135deg, #FEE2E2 0%, #FFE4E6 100%);
  border-color: rgba(239, 68, 68, 0.35);
}
.pp-tool-icon { font-size: 16px; }
.pp-tool-args-inline {
  flex: 1;
  font-family: var(--pp-font-mono, ui-monospace, "SF Mono", Menlo, monospace);
  font-size: 12px;
  color: var(--pp-color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.pp-tool-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
.pp-tool-name {
  font-weight: var(--pp-font-weight-semibold);
  color: var(--pp-color-text);
  font-size: var(--pp-font-size-sm);
}
.pp-tool-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 8px;
  border-radius: var(--pp-radius-full);
  font-size: 11px;
  font-weight: var(--pp-font-weight-medium);
  line-height: 18px;
}
.pp-tool-badge-running {
  background: var(--pp-color-primary-soft);
  color: var(--pp-color-primary);
  border: 1px solid rgba(91, 108, 255, 0.25);
}
.pp-tool-badge-success {
  background: var(--pp-color-success-soft);
  color: var(--pp-color-success);
  border: 1px solid rgba(16, 185, 129, 0.25);
}
.pp-tool-badge-danger {
  background: var(--pp-color-danger-soft);
  color: var(--pp-color-danger);
  border: 1px solid rgba(239, 68, 68, 0.25);
}
.pp-tool-time {
  color: var(--pp-color-text-tertiary);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  margin-left: auto;
}

/* tool collapse 面板：v0.37 紧凑 */
.pp-tool-collapse :deep(.ant-collapse-item) {
  border-bottom: none;
  margin-bottom: 0;
}
.pp-tool-collapse :deep(.ant-collapse-header) {
  padding: 0 !important;
  font-size: 11px;
  border-radius: 0;
  color: var(--pp-color-text-tertiary);
  min-height: 0 !important;
}
.pp-tool-collapse :deep(.ant-collapse-content) {
  border-radius: var(--pp-radius-sm);
  overflow: hidden;
}
.pp-tool-collapse :deep(.ant-collapse-content-box) {
  padding: 6px 8px !important;
}
.pp-tool-panel-input :deep(.ant-collapse-content) {
  background: var(--pp-color-surface);
  border: 1px solid var(--pp-color-border-soft);
}
.pp-tool-panel-result :deep(.ant-collapse-content) {
  background: #F0FDF4;
  border: 1px solid rgba(16, 185, 129, 0.2);
}
.pp-tool-pre {
  margin: 0;
  font-family: var(--pp-font-mono);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--pp-color-text);
}

/* ---------- thinking ---------- */
.pp-chat-thinking {
  /* v0.37: 铺满 + 单行高度 */
  width: 100%;
  color: var(--pp-color-text-secondary);
  font-style: italic;
  font-size: 11px;
  padding: 2px 10px;
  border-left: 2px solid var(--pp-color-border-strong);
  background: var(--pp-color-bg-elevated);
  border-radius: var(--pp-radius-sm);
  white-space: pre-wrap;
  line-height: 1.5;
}

/* ---------- error ---------- */
.pp-chat-error {
  max-width: 80%;
  background: var(--pp-color-danger-soft);
  border: 1px solid rgba(239, 68, 68, 0.25);
  color: var(--pp-color-danger);
  border-radius: var(--pp-radius-lg);
  padding: 8px 12px;
  font-size: var(--pp-font-size-xs);
  white-space: pre-wrap;
  box-shadow: var(--pp-shadow-sm);
}

/* ---------- v0.36 status bar：streaming 时常驻 ---------- */
.pp-chat-status {
  display: flex;
  align-items: center;
  gap: var(--pp-space-3);
  padding: 8px 14px;
  border-top: 1px solid var(--pp-color-border-soft);
  background: linear-gradient(90deg, rgba(91,108,255,0.05), rgba(91,108,255,0.02));
  font-size: var(--pp-font-size-sm);
}
.pp-chat-status-spinner {
  display: inline-flex;
  gap: 4px;
}
.pp-chat-status-spinner .pp-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--pp-color-primary);
  animation: pp-dot-bounce 1.2s infinite ease-in-out;
}
.pp-chat-status-spinner .pp-dot:nth-child(2) { animation-delay: 0.15s; }
.pp-chat-status-spinner .pp-dot:nth-child(3) { animation-delay: 0.3s; }
@keyframes pp-dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40%           { transform: scale(1.0); opacity: 1.0; }
}
.pp-chat-status-text {
  flex: 1;
  display: flex;
  gap: var(--pp-space-2);
  align-items: baseline;
  color: var(--pp-color-text-secondary);
  min-width: 0;
}
.pp-chat-status-phase {
  font-weight: var(--pp-font-weight-medium);
  color: var(--pp-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pp-chat-status-elapsed {
  font-size: var(--pp-font-size-xs);
  color: var(--pp-color-text-tertiary);
  font-variant-numeric: tabular-nums;
}

/* ---------- composer 输入区 ---------- */
.pp-chat-composer {
  padding: var(--pp-space-3);
  border-top: 1px solid var(--pp-color-border-soft);
  background: var(--pp-color-surface);
}
.pp-chat-mode-row {
  margin-bottom: var(--pp-space-2);
  display: flex;
  gap: var(--pp-space-2);
  align-items: center;
  font-size: var(--pp-font-size-xs);
  color: var(--pp-color-text-secondary);
}
.pp-chat-mode-tip { color: var(--pp-color-primary); }
.pp-chat-input-row {
  display: flex;
  gap: var(--pp-space-2);
}
</style>
