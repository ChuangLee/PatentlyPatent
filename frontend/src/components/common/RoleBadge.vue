<script setup lang="ts">
import { computed } from 'vue';
import type { Role } from '@/types';

const props = defineProps<{ role: Role | null }>();
const text = computed(() =>
  props.role === 'admin' ? '管理员' : props.role === 'employee' ? '员工' : '未登录',
);
const color = computed(() =>
  props.role === 'admin' ? 'gold' : props.role === 'employee' ? 'blue' : 'default',
);
</script>
<template>
  <a-tag :color="color" style="margin-left:8px">{{ text }}</a-tag>
</template>
