import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { ChatMessage } from '@/types';

const KEY_PREFIX = 'pp.chat.';

interface PersistShape {
  messages: ChatMessage[];
  capturedFields: string[];
}

export const useChatStore = defineStore('chat', () => {
  const projectId = ref<string | null>(null);
  const messages = ref<ChatMessage[]>([]);
  const streaming = ref(false);
  const capturedFields = ref<string[]>([]);

  function persist() {
    if (!projectId.value) return;
    const payload: PersistShape = {
      messages: messages.value,
      capturedFields: capturedFields.value,
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
      messages.value = cached.messages;
      capturedFields.value = cached.capturedFields ?? [];
    } else {
      messages.value = [];
      capturedFields.value = [];
    }
    streaming.value = false;
  }

  function appendUser(content: string) {
    messages.value.push({
      id: `m-${Date.now()}-u`,
      role: 'user',
      content,
      ts: new Date().toISOString(),
    });
    persist();
  }

  function startAgent() {
    messages.value.push({
      id: `m-${Date.now()}-a`,
      role: 'agent',
      content: '',
      ts: new Date().toISOString(),
    });
    streaming.value = true;
    // 流式中的空消息也持久化骨架，便于刷新看到上下文
    persist();
  }

  function appendDelta(chunk: string) {
    const last = messages.value[messages.value.length - 1];
    if (last && last.role === 'agent') {
      last.content += chunk;
      // 不在每个 delta 都写入（高频）；交由 endAgent 统一 persist
    }
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
    persist();
  }

  return {
    projectId, messages, streaming, capturedFields,
    attach, appendUser, startAgent, appendDelta, applyFields, endAgent, reset,
  };
});
