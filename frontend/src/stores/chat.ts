import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { ChatMessage } from '@/types';

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([]);
  const streaming = ref(false);
  const capturedFields = ref<string[]>([]);

  function appendUser(content: string) {
    messages.value.push({
      id: `m-${Date.now()}-u`,
      role: 'user',
      content,
      ts: new Date().toISOString(),
    });
  }

  function startAgent() {
    messages.value.push({
      id: `m-${Date.now()}-a`,
      role: 'agent',
      content: '',
      ts: new Date().toISOString(),
    });
    streaming.value = true;
  }

  function appendDelta(chunk: string) {
    const last = messages.value[messages.value.length - 1];
    if (last && last.role === 'agent') {
      last.content += chunk;
    }
  }

  function applyFields(captured: string[]) {
    capturedFields.value = [...capturedFields.value, ...captured];
  }

  function endAgent() {
    streaming.value = false;
  }

  function reset() {
    messages.value = [];
    streaming.value = false;
    capturedFields.value = [];
  }

  return {
    messages, streaming, capturedFields,
    appendUser, startAgent, appendDelta, applyFields, endAgent, reset,
  };
});
