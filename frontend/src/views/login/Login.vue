<script setup lang="ts">
import { useRouter } from 'vue-router';
import { authApi } from '@/api/auth';
import { useAuthStore } from '@/stores/auth';
import { message } from 'ant-design-vue';
import type { Role } from '@/types';

const router = useRouter();
const auth = useAuthStore();

async function loginAs(role: Role) {
  try {
    const user = await authApi.loginAs(role);
    auth.login(user);
    message.success(`已登录为 ${user.name}`);
    router.push(role === 'admin' ? '/admin/dashboard' : '/employee/dashboard');
  } catch (e) {
    message.error('登录失败：' + (e as Error).message);
  }
}
</script>

<template>
  <div style="display:flex;justify-content:center;align-items:center;min-height:100vh">
    <a-card title="PatentlyPatent · 原型演示" style="width:480px">
      <p style="color:#888;margin-bottom:24px">选择角色一键登录，无需密码（演示用）。</p>
      <div style="display:flex;gap:12px;flex-direction:column">
        <a-button type="primary" size="large" block @click="loginAs('employee')">
          👤 我是员工 — 报门 / 挖掘 / 起草交底书
        </a-button>
        <a-button size="large" block @click="loginAs('admin')">
          📊 我是管理员 — 看全量分布与项目
        </a-button>
      </div>
      <p style="color:#aaa;margin-top:32px;font-size:12px">
        本站 mock 数据驻留浏览器；刷新可重置。<br />
        部署：blind.pub/patent · 仓库：github.com/ChuangLee/PatentlyPatent
      </p>
    </a-card>
  </div>
</template>
