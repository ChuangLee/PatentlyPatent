import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { ChatMessage } from '@/types';

// v0.37: 数据格式改了（startAgent 不再预占位 + 顺序敏感），key 升 v2 强制旧缓存失效一次
const KEY_PREFIX = 'pp.chat.v2.';

// v0.36.5: agent 计划 step（update_plan 工具更新）
export interface PlanStep {
  id: string;
  title: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  note?: string;
}

interface PersistShape {
  messages: ChatMessage[];
  capturedFields: string[];
  // v0.34: detached agent run 的 id（断线重连用）
  currentRunId?: string | null;
  lastEventSeq?: number;
  // v0.36: interview phase 标志 + 是否可生成 docx 信号
  interviewActive?: boolean;
  readyForDocx?: boolean;
  // v0.36.5: 当前 plan 步骤列表
  currentPlan?: PlanStep[];
}

// v0.20 Wave1: 5 个章节的进度状态
export type SectionKey = 'prior_art' | 'summary' | 'embodiments' | 'claims' | 'drawings_description';
export type SectionStatus = 'pending' | 'running' | 'done' | 'error';

const DEFAULT_SECTION_PROGRESS: Record<SectionKey, SectionStatus> = {
  prior_art: 'pending',
  summary: 'pending',
  embodiments: 'pending',
  claims: 'pending',
  drawings_description: 'pending',
};

export const useChatStore = defineStore('chat', () => {
  const projectId = ref<string | null>(null);
  const messages = ref<ChatMessage[]>([]);
  const streaming = ref(false);
  const capturedFields = ref<string[]>([]);
  // v0.20 Wave1: section 进度（不持久化，每次 attach 复位）
  const sectionProgress = ref<Record<string, SectionStatus>>({ ...DEFAULT_SECTION_PROGRESS });
  // v0.34: detached agent run id（持久化到 sessionStorage，断线重连用）
  const currentRunId = ref<string | null>(null);
  const lastEventSeq = ref<number>(0);
  // v0.36: interview phase（mineFull 完成后开启）+ 可出 docx 信号
  const interviewActive = ref<boolean>(false);
  const readyForDocx = ref<boolean>(false);
  // v0.36: 后台工作进度——latest thinking 文本 + 工作开始时间戳（计时用）
  const latestPhase = ref<string>('');
  const workStartedAt = ref<number>(0);
  // v0.36: streaming 卡死自愈——记录最后一条 SSE event 时间，前端 watcher 检测超时
  const lastEventAt = ref<number>(0);
  // v0.36.5: 当前 plan 列表（update_plan 工具更新；in-place 替换）
  const currentPlan = ref<PlanStep[]>([]);

  function persist() {
    if (!projectId.value) return;
    const payload: PersistShape = {
      messages: messages.value,
      capturedFields: capturedFields.value,
      currentRunId: currentRunId.value,
      lastEventSeq: lastEventSeq.value,
      interviewActive: interviewActive.value,
      readyForDocx: readyForDocx.value,
      currentPlan: currentPlan.value,
    };
    sessionStorage.setItem(KEY_PREFIX + projectId.value, JSON.stringify(payload));
  }

  function load(pid: string): PersistShape | null {
    const raw = sessionStorage.getItem(KEY_PREFIX + pid);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as PersistShape;
      if (!parsed || !Array.isArray(parsed.messages)) return null;
      return parsed;
    } catch { return null; }
  }

  /**
   * 切换/绑定项目。
   * - 命中 sessionStorage：用缓存（流式状态强制 false，避免刷新后卡 streaming）
   * - 未命中：清空内存（让外部 caller 预填后调 persist），不预先存盘
   */
  function attach(pid: string) {
    projectId.value = pid;
    const cached = load(pid);
    if (cached) {
      // v0.18-C 兼容：老数据无 type 字段，回填 'text'
      let msgs = cached.messages.map(m => ({ ...m, type: m.type ?? 'text' }));
      // v0.37: 清掉所有空内容的 text agent 气泡（不只末尾）
      // 旧版 startAgent 会预占位空 bubble 在最早位置；新版不该有，残留就清
      msgs = msgs.filter(m => !(
        m.role === 'agent'
        && (m.type ?? 'text') === 'text'
        && (!m.content || m.content.trim() === '')
      ));
      messages.value = msgs;
      capturedFields.value = cached.capturedFields ?? [];
      currentRunId.value = cached.currentRunId ?? null;
      lastEventSeq.value = cached.lastEventSeq ?? 0;
      interviewActive.value = cached.interviewActive ?? false;
      readyForDocx.value = cached.readyForDocx ?? false;
      currentPlan.value = cached.currentPlan ?? [];
    } else {
      messages.value = [];
      capturedFields.value = [];
      currentRunId.value = null;
      lastEventSeq.value = 0;
      interviewActive.value = false;
      readyForDocx.value = false;
      currentPlan.value = [];
    }
    streaming.value = false;
    // section 进度每次 attach 复位
    sectionProgress.value = { ...DEFAULT_SECTION_PROGRESS };
  }

  function setCurrentRun(runId: string | null) {
    currentRunId.value = runId;
    if (runId === null) lastEventSeq.value = 0;
    persist();
  }

  function bumpLastSeq(seq: number) {
    if (seq > lastEventSeq.value) {
      lastEventSeq.value = seq;
      // 节流：每 10 个 event 才落一次盘，避免反复 sessionStorage write
      if (seq % 10 === 0) persist();
    }
  }

  /** v0.20 Wave1: 设置某个 section 的状态 */
  function setSectionStatus(key: string, status: SectionStatus) {
    sectionProgress.value = { ...sectionProgress.value, [key]: status };
  }

  /** v0.20 Wave1: 复位 section 进度（开新一轮挖掘前调） */
  function resetSectionProgress() {
    sectionProgress.value = { ...DEFAULT_SECTION_PROGRESS };
  }

  function appendUser(content: string) {
    messages.value.push({
      id: `m-${Date.now()}-u`,
      role: 'user',
      content,
      ts: new Date().toISOString(),
      type: 'text',
    });
    persist();
  }

  function startAgent() {
    // v0.37: 不再预创建空 text bubble（会被 thinking/tool 卡片"插队"挤到最上方）；
    // 让 appendDelta 第一次到达时再 push，自然落在所有 thinking/tool 之后
    streaming.value = true;
    workStartedAt.value = Date.now();
    lastEventAt.value = Date.now();
    latestPhase.value = '思考中';
    persist();
  }

  /** v0.36: 任意 SSE event 到达时调，更新最后活动时间；用于卡死自愈检测 */
  function bumpActivity() { lastEventAt.value = Date.now(); }
  /** v0.36: 设置最近一条 phase 文本（thinking/tool_use 触发） */
  function setLatestPhase(text: string) {
    latestPhase.value = text;
    lastEventAt.value = Date.now();
  }

  /** appendDelta 只追加到最近一条 type=text 的 agent 消息（跳过 tool_call/thinking 卡片） */
  function appendDelta(chunk: string) {
    // v0.37: 只复用"最后一条"消息——如果末尾正是 text agent 就续写；
    // 如果末尾是 tool/thinking（即中间有调用），起一条新 text bubble，
    // 这样视觉时序与事件时序对齐：每次工具调用之后 AI 续讲一段，单独成气泡
    const last = messages.value[messages.value.length - 1];
    if (last && last.role === 'agent' && (last.type ?? 'text') === 'text') {
      // splice 替换确保 Vue reactive trigger（minified build 下 in-place += 不稳）
      messages.value.splice(messages.value.length - 1, 1, { ...last, content: last.content + chunk });
      return;
    }
    messages.value.push({
      id: `m-${Date.now()}-d-${Math.random().toString(36).slice(2, 6)}`,
      role: 'agent',
      content: chunk,
      ts: new Date().toISOString(),
      type: 'text',
    });
  }

  /** v0.18-C: 推一条结构化 tool_call 消息（v0.20: 记 t0 用于耗时计算） */
  function appendToolCall(name: string, input: unknown, id?: string) {
    messages.value.push({
      id: `m-${Date.now()}-tc-${Math.random().toString(36).slice(2, 6)}`,
      role: 'agent',
      content: '',
      ts: new Date().toISOString(),
      type: 'tool_call',
      tool: { name, input, id, t0: Date.now() },
    });
    persist();
  }

  /** v0.18-C: 把 tool_result 挂到最近一条无 result 的 tool_call 上（v0.20: 算 tDurationMs）
   *  v0.36.8: 支持按 tool_use_id 精确匹配（并行多 tool_use 时不会错位） */
  function attachToolResult(text: string, data?: unknown, toolUseId?: string) {
    // 优先按 id 精确匹配
    if (toolUseId) {
      for (let i = messages.value.length - 1; i >= 0; i--) {
        const m = messages.value[i];
        if (m.type === 'tool_call' && m.tool && m.tool.id === toolUseId) {
          m.tool.result = text;
          if (data !== undefined) m.tool.data = data;
          if (m.tool.t0 != null) m.tool.tDurationMs = Date.now() - m.tool.t0;
          persist();
          return;
        }
      }
    }
    // fallback：最近一个无 result 的 tool_call
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const m = messages.value[i];
      if (m.type === 'tool_call' && m.tool && m.tool.result == null) {
        m.tool.result = text;
        if (data !== undefined) m.tool.data = data;
        if (m.tool.t0 != null) m.tool.tDurationMs = Date.now() - m.tool.t0;
        persist();
        return;
      }
    }
  }

  /** v0.18-C: 推一条 thinking 消息（agent 角色，独立卡片渲染） */
  function appendThinking(text: string) {
    messages.value.push({
      id: `m-${Date.now()}-th-${Math.random().toString(36).slice(2, 6)}`,
      role: 'agent',
      content: text,
      ts: new Date().toISOString(),
      type: 'thinking',
    });
    persist();
  }

  /** v0.18-C: 推一条 error 消息卡片 */
  function appendError(message: string) {
    messages.value.push({
      id: `m-${Date.now()}-er-${Math.random().toString(36).slice(2, 6)}`,
      role: 'agent',
      content: message,
      ts: new Date().toISOString(),
      type: 'error',
    });
    persist();
  }

  function applyFields(captured: string[]) {
    capturedFields.value = [...capturedFields.value, ...captured];
    persist();
  }

  function endAgent() {
    streaming.value = false;
    workStartedAt.value = 0;
    latestPhase.value = '';
    persist();
  }

  function reset() {
    messages.value = [];
    streaming.value = false;
    capturedFields.value = [];
    sectionProgress.value = { ...DEFAULT_SECTION_PROGRESS };
    interviewActive.value = false;
    readyForDocx.value = false;
    persist();
  }

  function setInterviewActive(v: boolean) { interviewActive.value = v; persist(); }
  function setReadyForDocx(v: boolean) { readyForDocx.value = v; persist(); }
  /** v0.37 harness: setPlan diff 检测；step 状态变 completed/failed 时自动 push 汇报气泡 */
  function setPlan(steps: PlanStep[]) {
    const oldById: Record<string, PlanStep> = {};
    for (const s of currentPlan.value) oldById[s.id] = s;
    const reports: Array<{ icon: string; title: string; failed: boolean }> = [];
    for (const s of steps) {
      const old = oldById[s.id];
      if (!old) continue;       // 新 step，本次不汇报
      if (old.status === s.status) continue;
      if (s.status === 'completed' && old.status !== 'completed') {
        reports.push({ icon: '✓', title: s.title, failed: false });
      } else if (s.status === 'failed' && old.status !== 'failed') {
        reports.push({ icon: '✗', title: s.title, failed: true });
      }
    }
    currentPlan.value = steps;
    // push 汇报消息（独立 type=step_done，不参与折叠合并）
    for (const r of reports) {
      messages.value.push({
        id: `m-${Date.now()}-step-${Math.random().toString(36).slice(2, 6)}`,
        role: 'agent',
        content: `${r.icon} ${r.title}`,
        ts: new Date().toISOString(),
        type: r.failed ? 'step_failed' : 'step_done',
      } as any);
    }
    persist();
  }
  function clearPlan() { currentPlan.value = []; persist(); }

  return {
    projectId, messages, streaming, capturedFields,
    attach, appendUser, startAgent, appendDelta, applyFields, endAgent, reset,
    // v0.18-C 结构化卡片
    appendToolCall, attachToolResult, appendThinking, appendError,
    // v0.20 Wave1 section 进度
    sectionProgress, setSectionStatus, resetSectionProgress,
    // v0.34: detached run 持久化
    currentRunId, lastEventSeq, setCurrentRun, bumpLastSeq,
    // v0.36: interview phase
    interviewActive, readyForDocx, setInterviewActive, setReadyForDocx,
    // v0.36: 后台进度
    latestPhase, workStartedAt, lastEventAt,
    bumpActivity, setLatestPhase,
    // v0.36.5: 工作计划
    currentPlan, setPlan, clearPlan,
  };
});
