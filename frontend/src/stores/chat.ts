import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { ChatMessage } from '@/types';

const KEY_PREFIX = 'pp.chat.';

interface PersistShape {
  messages: ChatMessage[];
  capturedFields: string[];
  // v0.34: detached agent run 的 id（断线重连用）
  currentRunId?: string | null;
  lastEventSeq?: number;
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

  function persist() {
    if (!projectId.value) return;
    const payload: PersistShape = {
      messages: messages.value,
      capturedFields: capturedFields.value,
      currentRunId: currentRunId.value,
      lastEventSeq: lastEventSeq.value,
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
      // v0.34.3 fix: 清掉末尾「空 agent 气泡」残留（上次 startAgent 但 SSE 中断没收到 delta）
      // 否则恢复进工作台时永远显示一个空气泡 + 卡住的 streaming 光标
      while (msgs.length) {
        const last = msgs[msgs.length - 1];
        const isStaleEmpty = last.role === 'agent'
          && (last.type ?? 'text') === 'text'
          && (!last.content || last.content.trim() === '');
        if (!isStaleEmpty) break;
        msgs = msgs.slice(0, -1);
      }
      messages.value = msgs;
      capturedFields.value = cached.capturedFields ?? [];
      currentRunId.value = cached.currentRunId ?? null;
      lastEventSeq.value = cached.lastEventSeq ?? 0;
    } else {
      messages.value = [];
      capturedFields.value = [];
      currentRunId.value = null;
      lastEventSeq.value = 0;
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
    messages.value.push({
      id: `m-${Date.now()}-a`,
      role: 'agent',
      content: '',
      ts: new Date().toISOString(),
      type: 'text',
    });
    streaming.value = true;
    // 流式中的空消息也持久化骨架，便于刷新看到上下文
    persist();
  }

  /** appendDelta 只追加到最近一条 type=text 的 agent 消息（跳过 tool_call/thinking 卡片） */
  function appendDelta(chunk: string) {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const m = messages.value[i];
      if (m.role === 'agent' && (m.type ?? 'text') === 'text') {
        // v0.34.4 fix: 用 splice 替换整个对象，确保 Vue reactive 一定 trigger 模板更新
        // 之前 in-place `m.content += chunk` 在某些 minified prod build 下 reactive 不稳
        messages.value.splice(i, 1, { ...m, content: m.content + chunk });
        return;
      }
      // 若中间夹了 tool_call/thinking 卡片就继续往上找最近的 text agent
    }
    // v0.34.4 fix: 如果找不到 text agent（例如 SSE 抢先于 startAgent 到达），
    // 自动 push 一条新 bubble 兜底，避免 delta 完全丢失
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

  /** v0.18-C: 把 tool_result 挂到最近一条无 result 的 tool_call 上（v0.20: 算 tDurationMs） */
  function attachToolResult(text: string, data?: unknown) {
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
    // 找不到就忽略（结构异常时不炸）
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
    persist();
  }

  function reset() {
    messages.value = [];
    streaming.value = false;
    capturedFields.value = [];
    sectionProgress.value = { ...DEFAULT_SECTION_PROGRESS };
    persist();
  }

  return {
    projectId, messages, streaming, capturedFields,
    attach, appendUser, startAgent, appendDelta, applyFields, endAgent, reset,
    // v0.18-C 结构化卡片
    appendToolCall, attachToolResult, appendThinking, appendError,
    // v0.20 Wave1 section 进度
    sectionProgress, setSectionStatus, resetSectionProgress,
    // v0.34: detached run 持久化
    currentRunId, lastEventSeq, setCurrentRun, bumpLastSeq,
  };
});
