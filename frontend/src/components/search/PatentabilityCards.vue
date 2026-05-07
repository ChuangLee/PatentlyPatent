<script setup lang="ts">
import type { Patentability } from '@/types';

const props = defineProps<{ value: Patentability; rationale: string }>();

const META: Record<Patentability, { label: string; color: string; icon: string }> = {
  strong:           { label: '很可能新颖',     color: '#16a34a', icon: '🟢' },
  moderate:         { label: '边缘',           color: '#d97706', icon: '🟡' },
  weak:             { label: '创造性存疑',     color: '#ea580c', icon: '🟠' },
  not_recommended:  { label: '建议不申请',     color: '#dc2626', icon: '🔴' },
};
</script>

<template>
  <a-row :gutter="16" style="margin-bottom:16px">
    <a-col v-for="(meta, key) in META" :key="key" :span="6">
      <a-card :body-style="{
        textAlign:'center', borderTop: `4px solid ${meta.color}`,
        opacity: key === value ? 1 : 0.4,
        boxShadow: key === value ? '0 4px 12px rgba(0,0,0,0.08)' : 'none',
      }">
        <div style="font-size:32px">{{ meta.icon }}</div>
        <div style="font-weight:bold;margin-top:8px">{{ meta.label }}</div>
        <div v-if="key === value" style="color:#666;font-size:12px;margin-top:8px">当前结论</div>
      </a-card>
    </a-col>
  </a-row>

  <a-alert :message="rationale" type="info" show-icon style="margin-bottom:24px">
    <template #description>
      <a-collapse ghost>
        <a-collapse-panel key="pro" header="👨‍💼 专业版（A22.3 三步法说理）">
          <p style="color:#666;font-size:13px;line-height:1.7">
            按《专利审查指南》2023 三步法：① 确定最接近现有技术；② 确定区别特征与本申请实际解决的技术问题；
            ③ 判断是否显而易见。本结论基于对 8 篇命中文献的整体评估，建议代理师人工复核 D1 选择。
          </p>
        </a-collapse-panel>
      </a-collapse>
    </template>
  </a-alert>
</template>
