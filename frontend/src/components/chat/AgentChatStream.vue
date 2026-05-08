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

const props = defineProps<{ projectId: string; round: number }>();
const emit = defineEmits<{ (e: 'roundComplete', captured: string[]): void }>();

const chat = useChatStore();
const files = useFilesStore();
const ui = useUIStore();
const auth = useAuthStore();
const input = ref('');
const containerRef = ref<HTMLElement | null>(null);
let currentAbort: AbortController | null = null;

function cancelStream() {
  if (currentAbort) {
    currentAbort.abort();
    currentAbort = null;
    chat.endAgent();
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
  chat.startAgent();
  currentAbort = new AbortController();
  const useAgentSdk = ui.agentMode === 'agent_sdk';
  try {
    const handler = (e: import('@/types').ChatStreamEvent) => {
      if (e.type === 'delta') chat.appendDelta(e.chunk);
      else if (e.type === 'thinking' && e.text) chat.appendDelta(`\n💭 ${e.text}\n`);
      else if (e.type === 'tool_use') chat.appendDelta(`\n🔧 调 ${e.name}(${JSON.stringify(e.input)})\n`);
      else if (e.type === 'tool_result') chat.appendDelta(`\n→ ${e.text}\n`);
      else if (e.type === 'error') chat.appendDelta(`\n❌ ${e.message}\n`);
      else if (e.type === 'file') {
        const existing = files.tree.find(n => n.id === e.node.id);
        if (existing) Object.assign(existing, e.node);
        else files.pushNode(e.node);
        files.selectFile(e.node.id);
      }
      else if (e.type === 'done') chat.endAgent();
    };
    if (useAgentSdk) {
      const idea = [ctx.title, ctx.description, ctx.intake?.notes].filter(Boolean).join('\n');
      await chatApi.agentMineSpike(idea || '（无描述）', handler, currentAbort.signal);
    } else {
      await chatApi.autoMine(props.projectId, ctx, handler, currentAbort.signal);
    }
  } finally {
    currentAbort = null;
  }
}

defineExpose({ autoMine });
</script>

<template>
  <div style="display:flex;flex-direction:column;height:100%">
    <div ref="containerRef" style="flex:1;overflow-y:auto;padding:16px;background:#fafafa">
      <div v-if="chat.messages.length === 0" style="color:#aaa;text-align:center;padding-top:80px">
        尚未开始对话——发送第一条消息让 AI 开始引导。
      </div>
      <div v-for="m in chat.messages" :key="m.id"
           :style="{
             marginBottom: '16px',
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
