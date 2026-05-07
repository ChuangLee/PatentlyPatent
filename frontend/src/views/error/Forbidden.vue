<script setup lang="ts">
import { useRouter } from 'vue-router';
const router = useRouter();
</script>
<template>
  <a-result status="403" title="403" sub-title="你没有访问此页面的权限">
    <template #extra>
      <a-button type="primary" @click="router.push('/login')">回登录页</a-button>
    </template>
  </a-result>
</template>
