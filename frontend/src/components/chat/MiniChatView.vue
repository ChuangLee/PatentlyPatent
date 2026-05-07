<script setup lang="ts">
/**
 * MiniChatView — split view 模式下的伴随聊天预览
 * 只读、无输入框，显示最近 N 条对话，自动滚到底部
 */
import { computed, nextTick, ref, watch } from 'vue';
import { useChatStore } from '@/stores/chat';

const props = withDefaults(defineProps<{ tail?: number }>(), { tail: 8 });

const chat = useChatStore();
const scrollRef = ref<HTMLDivElement | null>(null);

const recent = computed(() => {
  const n = props.tail ?? 8;
  return chat.messages.slice(-n);
});

watch(
  () => [chat.messages.length, recent.value[recent.value.length - 1]?.content],
  async () => {
    await nextTick();
    const el = scrollRef.value;
    if (el) el.scrollTop = el.scrollHeight;
  },
);
</script>

<template>
  <div class="pp-mini-chat">
    <div class="pp-mini-chat-head">
      <span class="pp-mini-chat-title">💬 对话伴随</span>
      <span v-if="chat.streaming" class="pp-mini-chat-streaming">● streaming</span>
      <span class="pp-mini-chat-count">最近 {{ recent.length }} 条</span>
    </div>
    <div ref="scrollRef" class="pp-mini-chat-body">
      <div v-if="recent.length === 0" class="pp-mini-chat-empty">
        暂无对话内容
      </div>
      <div
        v-for="m in recent"
        :key="m.id"
        class="pp-mini-msg"
        :class="m.role === 'user' ? 'pp-mini-msg-user' : 'pp-mini-msg-agent'"
      >
        <div class="pp-mini-msg-role">{{ m.role === 'user' ? '我' : 'AI' }}</div>
        <div class="pp-mini-msg-content">
          {{ m.content || (chat.streaming ? '…' : '') }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pp-mini-chat {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #fafbfc;
}
.pp-mini-chat-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-bottom: 1px solid #eee;
  background: #fff;
  font-size: 12px;
}
.pp-mini-chat-title {
  font-weight: 600;
  color: #1f2937;
}
.pp-mini-chat-streaming {
  color: #1677ff;
  font-size: 11px;
  animation: pp-blink 1.2s infinite;
}
.pp-mini-chat-count {
  margin-left: auto;
  color: #9ca3af;
  font-size: 11px;
}
.pp-mini-chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.pp-mini-chat-empty {
  color: #aaa;
  text-align: center;
  margin-top: 30px;
  font-size: 12px;
}
.pp-mini-msg {
  display: flex;
  gap: 6px;
  font-size: 12px;
  line-height: 1.5;
}
.pp-mini-msg-role {
  flex: 0 0 26px;
  font-weight: 600;
  font-size: 11px;
  padding-top: 2px;
}
.pp-mini-msg-content {
  flex: 1;
  padding: 4px 8px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  min-width: 0;
}
.pp-mini-msg-user .pp-mini-msg-role { color: #1677ff; }
.pp-mini-msg-user .pp-mini-msg-content {
  background: #e6f1ff;
  color: #0b3a78;
}
.pp-mini-msg-agent .pp-mini-msg-role { color: #16a34a; }
.pp-mini-msg-agent .pp-mini-msg-content {
  background: #fff;
  border: 1px solid #eef2f7;
  color: #1f2937;
}
@keyframes pp-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
</style>
