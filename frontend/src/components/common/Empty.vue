<script setup lang="ts">
import { useRoute } from 'vue-router';
const route = useRoute();
</script>
<template>
  <div style="padding:48px;text-align:center;color:#888;font-family:monospace">
    [Empty placeholder] {{ route.fullPath }}
  </div>
</template>
