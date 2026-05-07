<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { useChatStore } from '@/stores/chat';
import { useFilesStore } from '@/stores/files';
import { chatApi } from '@/api/chat';
import { Button, Input } from 'ant-design-vue';

const props = defineProps<{ projectId: string; round: number }>();
const emit = defineEmits<{ (e: 'roundComplete', captured: string[]): void }>();

const chat = useChatStore();
const files = useFilesStore();
const input = ref('');
const containerRef = ref<HTMLElement | null>(null);

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

  await chatApi.stream(props.projectId, props.round, text, e => {
    if (e.type === 'delta') chat.appendDelta(e.chunk);
    else if (e.type === 'fields') {
      chat.applyFields(e.captured);
      emit('roundComplete', e.captured);
    } else if (e.type === 'file') {
      // AI 在文件树上 spawn 文件
      files.pushNode(e.node);
    } else if (e.type === 'done') {
      chat.endAgent();
    }
  });
}

/** 由父组件（ProjectWorkbench）调，进入工作台时自动跑挖掘流程 */
async function autoMine(ctx: Parameters<typeof chatApi.autoMine>[1]) {
  if (chat.streaming) return;
  chat.startAgent();
  await chatApi.autoMine(props.projectId, ctx, e => {
    if (e.type === 'delta') chat.appendDelta(e.chunk);
    else if (e.type === 'file') files.pushNode(e.node);
    else if (e.type === 'done') chat.endAgent();
  });
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
      <div style="display:flex;gap:8px">
        <Input v-model:value="input" placeholder="描述你的发明，或回答 AI 的问题..."
               :disabled="chat.streaming" @press-enter="send" />
        <Button type="primary" :loading="chat.streaming" @click="send">发送</Button>
      </div>
    </div>
  </div>
</template>
