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
import Tag from 'ant-design-vue/es/tag';
import Collapse from 'ant-design-vue/es/collapse';
import Spin from 'ant-design-vue/es/spin';

const CollapsePanel = Collapse.Panel;

function fmtToolInput(v: unknown): string {
  try { return JSON.stringify(v, null, 2); } catch { return String(v); }
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
  <div style="display:flex;flex-direction:column;height:100%">
    <div ref="containerRef" style="flex:1;overflow-y:auto;padding:16px;background:#fafafa">
      <div v-if="chat.messages.length === 0" style="color:#aaa;text-align:center;padding-top:80px">
        尚未开始对话——发送第一条消息让 AI 开始引导。
      </div>
      <template v-for="m in chat.messages" :key="m.id">
        <!-- text bubble（默认；老数据 type 为 undefined 也走这里） -->
        <div v-if="(m.type ?? 'text') === 'text'"
             :style="{
               marginBottom: '12px',
               display:'flex',
               justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
             }">
          <div :style="{
            maxWidth: '70%',
            background: m.role === 'user' ? '#1677ff' : '#fff',
            color: m.role === 'user' ? '#fff' : '#1f2937',
            padding: '10px 14px', borderRadius: '12px',
            whiteSpace: 'pre-wrap', boxShadow: '0 1px 2px rgba(0,0,0,.06)',
          }">
            <span>{{ m.content }}</span>
            <span v-if="m.role === 'agent' && chat.streaming
                        && m.id === chat.messages[chat.messages.length-1].id"
                  style="opacity:.4">|</span>
          </div>
        </div>

        <!-- tool_call 卡片（浅蓝；result 用 collapse 折叠） -->
        <div v-else-if="m.type === 'tool_call' && m.tool"
             style="margin-bottom:10px;display:flex;justify-content:flex-start">
          <div style="max-width:80%;width:100%;background:#f0f7ff;border:1px solid #d6e4ff;
                      border-radius:8px;padding:8px 10px;font-size:12px">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
              <Tag color="processing" style="margin:0">🔧 {{ m.tool.name }}</Tag>
              <span v-if="m.tool.tDurationMs != null" class="pp-tool-time">⏱ {{ m.tool.tDurationMs }}ms</span>
              <span v-if="m.tool.result == null" style="color:#1677ff;font-size:11px;display:inline-flex;align-items:center;gap:4px">
                <Spin size="small" />
                运行中…
              </span>
              <span v-else style="color:#52c41a;font-size:11px">✓ 完成</span>
            </div>
            <Collapse :bordered="false" ghost size="small">
              <CollapsePanel key="input" header="入参">
                <pre style="margin:0;font-size:11px;white-space:pre-wrap;word-break:break-all">{{ fmtToolInput(m.tool.input) }}</pre>
              </CollapsePanel>
              <CollapsePanel v-if="m.tool.result != null" key="result" header="结果"
                             :style="{ background: '#f6ffed' }">
                <pre style="margin:0;font-size:11px;white-space:pre-wrap;word-break:break-all">{{ m.tool.result }}</pre>
              </CollapsePanel>
            </Collapse>
          </div>
        </div>

        <!-- thinking：浅灰 italic -->
        <div v-else-if="m.type === 'thinking'"
             style="margin-bottom:8px;display:flex;justify-content:flex-start">
          <div style="max-width:80%;color:#8c8c8c;font-style:italic;font-size:12px;
                      padding:4px 10px;border-left:2px solid #d9d9d9;background:#fafafa;
                      white-space:pre-wrap">
            💭 {{ m.content }}
          </div>
        </div>

        <!-- error 卡片 -->
        <div v-else-if="m.type === 'error'"
             style="margin-bottom:10px;display:flex;justify-content:flex-start">
          <div style="max-width:80%;background:#fff2f0;border:1px solid #ffccc7;
                      color:#cf1322;border-radius:8px;padding:8px 12px;font-size:12px;
                      white-space:pre-wrap">
            ❌ {{ m.content }}
          </div>
        </div>
      </template>
    </div>

    <div style="padding:12px;border-top:1px solid #eee;background:#fff">
      <!-- v0.17-D: admin 才能看到 agent 模式切换 -->
      <div v-if="auth.role === 'admin'" style="margin-bottom:8px;display:flex;gap:8px;align-items:center;font-size:12px;color:#666">
        <span>挖掘内核：</span>
        <Segmented :value="ui.agentMode"
                   :options="[{label:'老 mining',value:'mining'},{label:'Agent SDK',value:'agent_sdk'}]"
                   :disabled="chat.streaming"
                   @change="(v: any) => ui.setAgentMode(v as 'mining' | 'agent_sdk')" />
        <span v-if="ui.agentMode === 'agent_sdk'" style="color:#1677ff">⚡ spike 端点</span>
      </div>
      <div style="display:flex;gap:8px">
        <Input v-model:value="input" placeholder="描述你的发明，或回答 AI 的问题..."
               :disabled="chat.streaming" @press-enter="send" />
        <Button type="primary" :loading="chat.streaming" @click="send">发送</Button>
        <Button v-if="chat.streaming" danger @click="cancelStream">🛑 取消</Button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* v0.20 Wave1 任务 2: tool_call 耗时小字 */
.pp-tool-time {
  color: #bfbfbf;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
</style>
