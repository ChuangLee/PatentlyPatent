<script setup lang="ts">
defineProps<{ show: boolean }>();
</script>
<template>
  <a-alert v-if="show" type="warning" show-icon banner
           message="只读模式 (admin 视角)"
           description="您正在以管理员身份查看员工项目，所有编辑/提交按钮已隐藏。" />
</template>
