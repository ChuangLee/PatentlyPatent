<script setup lang="ts">
import { computed } from 'vue';
import { useChatStore } from '@/stores/chat';

const chat = useChatStore();

const groups = computed(() => {
  const g: Record<string, string[]> = { 领域: [], 问题: [], 手段: [], 效果: [], 区别: [] };
  for (const f of chat.capturedFields) {
    const [k, ...rest] = f.split(':');
    const v = rest.join(':');
    if (k in g) g[k].push(v);
  }
  return g;
});
</script>

<template>
  <div style="padding:16px">
    <h3 style="margin:0 0 16px 0">📌 已捕获要素</h3>
    <a-card v-for="(items, key) in groups" :key="key" size="small" style="margin-bottom:12px">
      <template #title>
        <span>{{ key }}</span>
        <a-badge :status="items.length ? 'success' : 'default'" style="margin-left:8px" />
      </template>
      <p v-if="items.length === 0" style="color:#aaa;margin:0">未捕获</p>
      <a-tag v-for="(item, i) in items" :key="i" color="blue" style="margin-bottom:4px">
        {{ item }}
      </a-tag>
    </a-card>
  </div>
</template>
