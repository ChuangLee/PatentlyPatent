<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { useAuthStore } from '@/stores/auth';
import { message } from 'ant-design-vue';
import type { Domain } from '@/types';

const router = useRouter();
const auth = useAuthStore();
const submitting = ref(false);

const form = reactive({
  title: '',
  description: '',
  domain: 'other' as Domain,
});

const DOMAINS: { value: Domain; label: string }[] = [
  { value: 'cryptography', label: '密码学' },
  { value: 'infosec', label: '信息安全' },
  { value: 'ai', label: '人工智能' },
  { value: 'other', label: '其他' },
];

async function submit() {
  if (!form.title.trim() || form.description.length < 30) {
    message.warning('标题不能为空，描述至少 30 字');
    return;
  }
  submitting.value = true;
  try {
    const p = await projectsApi.create({
      title: form.title,
      description: form.description,
      domain: form.domain,
      ownerId: auth.user!.id,
    });
    message.success('已创建，进入 AI 引导对话');
    router.push(`/employee/projects/${p.id}/mining`);
  } catch (e) {
    message.error('创建失败：' + (e as Error).message);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <a-page-header title="新建创新报门" @back="router.back()" />

  <a-form layout="vertical" style="max-width:720px">
    <a-form-item label="项目标题（10–50 字）" required>
      <a-input v-model:value="form.title" placeholder="例：基于 SIMD 的 Kyber-512 NTT 优化"
               :maxlength="50" show-count />
    </a-form-item>

    <a-form-item label="技术领域" required>
      <a-select v-model:value="form.domain">
        <a-select-option v-for="d in DOMAINS" :key="d.value" :value="d.value">
          {{ d.label }}
        </a-select-option>
      </a-select>
    </a-form-item>

    <a-form-item label="一句话或几段描述（≥30 字，越详细 AI 引导越准）" required>
      <a-textarea v-model:value="form.description" :rows="6"
                  placeholder="例：我们在 ARM Cortex-M4 上对 Kyber-512 NTT 做了 SIMD 两路并行..." />
    </a-form-item>

    <a-form-item>
      <a-button type="primary" :loading="submitting" @click="submit">提交并进入 AI 引导 →</a-button>
    </a-form-item>
  </a-form>
</template>
