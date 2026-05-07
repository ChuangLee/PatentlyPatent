<script setup lang="ts">
import type { PriorArtHit } from '@/types';
import { ref } from 'vue';

defineProps<{ hits: PriorArtHit[] }>();

const expanded = ref<string[]>([]);
const drawerHit = ref<PriorArtHit | null>(null);

const XYN_META = {
  X: { color: 'red', label: 'X · 破新颖' },
  Y: { color: 'orange', label: 'Y · 创造性结合' },
  N: { color: 'default', label: 'N · 不相关' },
} as const;

const columns = [
  { title: '公开号', dataIndex: 'id', width: 160 },
  { title: '标题', dataIndex: 'title', ellipsis: true },
  { title: '申请人', dataIndex: 'applicant', width: 140 },
  { title: '公布日', dataIndex: 'pubDate', width: 110 },
  { title: 'X/Y/N', dataIndex: 'xyn', width: 130, key: 'xyn' },
  { title: '操作', key: 'op', width: 120 },
];
</script>

<template>
  <a-table :data-source="hits" :columns="columns" :pagination="false" row-key="id"
           :expandable="{ expandedRowKeys: expanded, onExpandedRowsChange: (k: (string | number)[]) => expanded = k as string[] }">
    <template #bodyCell="{ column, record }: { column: { key: string }, record: PriorArtHit }">
      <template v-if="column.key === 'xyn'">
        <a-tag :color="XYN_META[record.xyn].color">{{ XYN_META[record.xyn].label }}</a-tag>
      </template>
      <template v-else-if="column.key === 'op'">
        <a-button type="link" size="small" @click="drawerHit = record">详情 →</a-button>
      </template>
    </template>
    <template #expandedRowRender="{ record }: { record: PriorArtHit }">
      <a-row :gutter="16">
        <a-col :span="8">
          <strong>📌 问题对比</strong>
          <p>{{ record.comparison.problem }}</p>
        </a-col>
        <a-col :span="8">
          <strong>🔧 手段对比</strong>
          <p>{{ record.comparison.means }}</p>
        </a-col>
        <a-col :span="8">
          <strong>🎯 效果对比</strong>
          <p>{{ record.comparison.effect }}</p>
        </a-col>
      </a-row>
    </template>
  </a-table>

  <a-drawer :open="!!drawerHit" :title="drawerHit?.title" width="640" @close="drawerHit = null">
    <p><strong>公开号：</strong>{{ drawerHit?.id }}</p>
    <p><strong>申请人：</strong>{{ drawerHit?.applicant }}</p>
    <p><strong>公布日：</strong>{{ drawerHit?.pubDate }}</p>
    <p><strong>IPC：</strong>{{ drawerHit?.ipc.join(', ') }}</p>
    <a-divider />
    <p><strong>摘要：</strong></p>
    <p style="color:#555;line-height:1.7;white-space:pre-wrap">{{ drawerHit?.abstract }}</p>
  </a-drawer>
</template>
