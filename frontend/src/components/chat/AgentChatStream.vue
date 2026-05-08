<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
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

const CollapsePanel = Collapse.Panel;

function fmtToolInput(v: unknown): string {
  try { return JSON.stringify(v, null, 2); } catch { return String(v); }
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
const files = useFilesStore();
const ui = useUIStore();
const auth = useAuthStore();
const input = ref('');
const containerRef = ref<HTMLElement | null>(null);
let currentAbort: AbortController | null = null;
// v0.20 Wave1 任务 3: 防抖 ref——只在第一次 file 事件时自动开 split view
const splitAutoOpened = ref(false);

function cancelStream() {
  if (currentAbort) {
    currentAbort.abort();
    currentAbort = null;
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
  if (chat.streaming) return;
  // v0.20 Wave1: 新一轮挖掘前复位 section 进度
  chat.resetSectionProgress();
  chat.startAgent();
  currentAbort = new AbortController();
  const useAgentSdk = ui.agentMode === 'agent_sdk';
  try {
    const handler = (e: import('@/types').ChatStreamEvent) => {
      if (e.type === 'delta') chat.appendDelta(e.chunk);
      else if (e.type === 'thinking' && e.text) chat.appendThinking(e.text);
      else if (e.type === 'tool_use') chat.appendToolCall(e.name, e.input, e.id);
      else if (e.type === 'tool_result') chat.attachToolResult(e.text, e.data);
      else if (e.type === 'error') chat.appendError(e.message);
      else if (e.type === 'file') {
        const existing = files.tree.find(n => n.id === e.node.id);
        if (existing) Object.assign(existing, e.node);
        else files.pushNode(e.node);
        files.selectFile(e.node.id);
        files.markSpawnedNode(e.node.id);  // v0.21 任务 4: 触发 FileTree 滚动
        autoOpenSplitOnFirstFile();
      }
      // v0.20 Wave1 任务 1: section_start / section_done 由后端 mine_full SSE 推送
      // 注意：这些事件类型未在 ChatStreamEvent union 中声明，但 SSE handler 会透传。
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      else if ((e as any).type === 'section_start' && (e as any).section) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        chat.setSectionStatus((e as any).section, 'running');
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      else if ((e as any).type === 'section_done' && (e as any).section) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        chat.setSectionStatus((e as any).section, 'done');
      }
      else if (e.type === 'done') chat.endAgent();
    };
    if (useAgentSdk) {
      // v0.21 任务 2: agent_sdk 模式从 mine_spike 切到 mine_full（端到端 5 节）
      const idea = [ctx.title, ctx.description, ctx.intake?.notes].filter(Boolean).join('\n');
      try {
        await chatApi.mineFullStream(props.projectId, idea || '（无描述）', handler, currentAbort.signal);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        // 兜底：仅提示，不再退回老 auto-mining，避免左右横跳
        const { default: antMessage } = await import('ant-design-vue/es/message');
        antMessage.error(`mine_full 失败：${msg}`);
        chat.appendError(`mine_full 失败：${msg}`);
        chat.endAgent();
      }
    } else {
      await chatApi.autoMine(props.projectId, ctx, handler, currentAbort.signal);
    }
  } finally {
    currentAbort = null;
  }
}

/** v0.21 任务 1: 一键全程挖掘 — agent_sdk 模式专用，由父组件按钮触发 */
async function mineFull(idea: string) {
  if (chat.streaming) return;
  chat.resetSectionProgress();
  chat.startAgent();
  currentAbort = new AbortController();
  try {
    const handler = (e: import('@/types').ChatStreamEvent) => {
      if (e.type === 'delta') chat.appendDelta(e.chunk);
      else if (e.type === 'thinking' && e.text) chat.appendThinking(e.text);
      else if (e.type === 'tool_use') chat.appendToolCall(e.name, e.input, e.id);
      else if (e.type === 'tool_result') chat.attachToolResult(e.text, e.data);
      else if (e.type === 'error') chat.appendError(e.message);
      else if (e.type === 'file') {
        const existing = files.tree.find(n => n.id === e.node.id);
        if (existing) Object.assign(existing, e.node);
        else files.pushNode(e.node);
        files.selectFile(e.node.id);
        files.markSpawnedNode(e.node.id);  // v0.21 任务 4: 触发 FileTree 滚动
        autoOpenSplitOnFirstFile();
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      else if ((e as any).type === 'section_start' && (e as any).section) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        chat.setSectionStatus((e as any).section, 'running');
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      else if ((e as any).type === 'section_done' && (e as any).section) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        chat.setSectionStatus((e as any).section, 'done');
      }
      else if (e.type === 'done') chat.endAgent();
    };
    await chatApi.mineFullStream(props.projectId, idea || '（无描述）', handler, currentAbort.signal);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const { default: antMessage } = await import('ant-design-vue/es/message');
    antMessage.error(`一键挖掘失败：${msg}`);
    chat.appendError(`一键挖掘失败：${msg}`);
    chat.endAgent();
    throw err;
  } finally {
    currentAbort = null;
  }
}

defineExpose({ autoMine, mineFull });
</script>

<template>
  <div class="pp-chat-root">
    <div ref="containerRef" class="pp-chat-stream">
      <div v-if="chat.messages.length === 0" class="pp-chat-empty">
        尚未开始对话——发送第一条消息让 AI 开始引导。
      </div>
      <template v-for="m in chat.messages" :key="m.id">
        <!-- text bubble（默认；老数据 type 为 undefined 也走这里） -->
        <div v-if="(m.type ?? 'text') === 'text'"
             class="pp-chat-row"
             :class="m.role === 'user' ? 'pp-chat-row-user' : 'pp-chat-row-agent'">
          <!-- agent avatar：左侧 28px 渐变圆形 + 'AI' -->
          <div v-if="m.role !== 'user'" class="pp-chat-avatar" aria-hidden="true">AI</div>

          <div class="pp-chat-bubble-wrap">
            <div class="pp-chat-bubble"
                 :class="m.role === 'user' ? 'pp-chat-bubble-user' : 'pp-chat-bubble-agent'">
              <span>{{ m.content }}</span>
              <span v-if="m.role === 'agent' && chat.streaming
                          && m.id === chat.messages[chat.messages.length-1].id"
                    class="pp-chat-cursor">|</span>
            </div>
            <div v-if="m.ts" class="pp-chat-timestamp"
                 :class="{ 'pp-chat-timestamp-right': m.role === 'user' }">
              {{ fmtTs(m.ts) }}
            </div>
          </div>
        </div>

        <!-- tool_call 卡片（渐变 primary→pink；状态徽章；result 浅绿折叠） -->
        <div v-else-if="m.type === 'tool_call' && m.tool"
             class="pp-chat-row pp-chat-row-agent">
          <div class="pp-tool-card">
            <div class="pp-tool-head">
              <span class="pp-tool-name">🔧 {{ m.tool.name }}</span>
              <span v-if="(m.tool as any).status === 'error'"
                    class="pp-tool-badge pp-tool-badge-danger">✗ 失败</span>
              <span v-else-if="m.tool.result == null"
                    class="pp-tool-badge pp-tool-badge-running">
                <Spin size="small" />
                运行中
              </span>
              <span v-else class="pp-tool-badge pp-tool-badge-success">✓ 完成</span>
              <span v-if="m.tool.tDurationMs != null" class="pp-tool-time">⏱ {{ m.tool.tDurationMs }}ms</span>
            </div>
            <Collapse :bordered="false" ghost size="small" class="pp-tool-collapse">
              <CollapsePanel key="input" header="入参" class="pp-tool-panel-input">
                <pre class="pp-tool-pre">{{ fmtToolInput(m.tool.input) }}</pre>
              </CollapsePanel>
              <CollapsePanel v-if="m.tool.result != null" key="result" header="结果"
                             class="pp-tool-panel-result">
                <pre class="pp-tool-pre">{{ m.tool.result }}</pre>
              </CollapsePanel>
            </Collapse>
          </div>
        </div>

        <!-- thinking：浅灰 italic -->
        <div v-else-if="m.type === 'thinking'" class="pp-chat-row pp-chat-row-agent">
          <div class="pp-chat-thinking">💭 {{ m.content }}</div>
        </div>

        <!-- error 卡片 -->
        <div v-else-if="m.type === 'error'" class="pp-chat-row pp-chat-row-agent">
          <div class="pp-chat-error">❌ {{ m.content }}</div>
        </div>
      </template>
    </div>

    <div class="pp-chat-composer">
      <!-- v0.17-D: admin 才能看到 agent 模式切换 -->
      <div v-if="auth.role === 'admin'" class="pp-chat-mode-row">
        <span>挖掘内核：</span>
        <Segmented :value="ui.agentMode"
                   :options="[{label:'老 mining',value:'mining'},{label:'Agent SDK',value:'agent_sdk'}]"
                   :disabled="chat.streaming"
                   @change="(v: any) => ui.setAgentMode(v as 'mining' | 'agent_sdk')" />
        <span v-if="ui.agentMode === 'agent_sdk'" class="pp-chat-mode-tip">⚡ spike 端点</span>
      </div>
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
  margin-bottom: var(--pp-space-4);
}
.pp-chat-row-user { justify-content: flex-end; }
.pp-chat-row-agent { justify-content: flex-start; }

/* ---------- agent avatar：28px 渐变圆 + 'AI' 字 ---------- */
.pp-chat-avatar {
  flex: none;
  width: 28px;
  height: 28px;
  border-radius: var(--pp-radius-full);
  background: linear-gradient(135deg, var(--pp-color-primary) 0%, #8B5CF6 50%, #EC4899 100%);
  color: #fff;
  font-size: 11px;
  font-weight: var(--pp-font-weight-bold);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0.5px;
  box-shadow: var(--pp-shadow-sm);
  margin-top: 2px;
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
  padding: 10px 14px;
  border-radius: var(--pp-radius-lg);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: var(--pp-font-size-base);
  line-height: var(--pp-line-height-normal);
}

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
.pp-tool-card {
  max-width: 80%;
  width: 100%;
  background: linear-gradient(135deg, #EEF0FF 0%, #FCE7F3 100%);
  border: 1px solid rgba(91, 108, 255, 0.2);
  border-radius: var(--pp-radius-lg);
  padding: 10px 12px;
  font-size: var(--pp-font-size-xs);
  box-shadow: var(--pp-shadow-sm);
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

/* tool collapse 面板：白底/浅绿 + monospace */
.pp-tool-collapse :deep(.ant-collapse-item) {
  border-bottom: none;
  margin-bottom: 6px;
}
.pp-tool-collapse :deep(.ant-collapse-header) {
  padding: 4px 8px !important;
  font-size: 12px;
  border-radius: var(--pp-radius-md);
  color: var(--pp-color-text-secondary);
}
.pp-tool-collapse :deep(.ant-collapse-content) {
  border-radius: var(--pp-radius-md);
  overflow: hidden;
}
.pp-tool-collapse :deep(.ant-collapse-content-box) {
  padding: 8px 10px !important;
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
  max-width: 80%;
  color: var(--pp-color-text-secondary);
  font-style: italic;
  font-size: var(--pp-font-size-xs);
  padding: 4px 10px;
  border-left: 2px solid var(--pp-color-border-strong);
  background: var(--pp-color-bg-elevated);
  border-radius: var(--pp-radius-sm);
  white-space: pre-wrap;
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
