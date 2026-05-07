<script setup lang="ts">
import { computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useUIStore } from '@/stores/ui';
import RoleBadge from '@/components/common/RoleBadge.vue';

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const ui = useUIStore();

interface MenuItem { key: string; label: string; icon?: string; disabled?: boolean }

const menuItems = computed<MenuItem[]>(() => {
  if (auth.role === 'admin') {
    return [
      { key: '/admin/dashboard', label: '总览', icon: '📊' },
      { key: '/admin/projects', label: '全量项目', icon: '📋' },
      { key: 'sep', label: '— 浏览员工视图 —', disabled: true },
      { key: '/employee/dashboard', label: '员工工作台', icon: '👤' },
    ];
  }
  return [
    { key: '/employee/dashboard', label: '我的项目', icon: '📋' },
    { key: '/employee/projects/new', label: '+ 新建报门', icon: '✨' },
  ];
});

const selectedKeys = computed(() => [route.path]);

function onMenuClick({ key }: { key: string }) {
  if (key !== 'sep') router.push(key);
}

function logout() {
  auth.logout();
  router.push('/login');
}
</script>

<template>
  <a-layout style="min-height:100vh">
    <a-layout-sider :collapsed="ui.sidebarCollapsed" collapsible
                    @update:collapsed="ui.toggleSidebar()" theme="light">
      <div style="padding:16px;text-align:center;border-bottom:1px solid #eee">
        <strong>PatentlyPatent</strong>
      </div>
      <a-menu :selected-keys="selectedKeys" mode="inline" @click="onMenuClick">
        <template v-for="item in menuItems" :key="item.key">
          <a-menu-item v-if="!item.disabled" :key="item.key">
            <span>{{ item.icon }} {{ item.label }}</span>
          </a-menu-item>
          <a-menu-divider v-else />
        </template>
      </a-menu>
    </a-layout-sider>
    <a-layout>
      <a-layout-header style="background:#fff;padding:0 24px;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center">
        <span>{{ route.meta.title || '' }}</span>
        <span>
          {{ auth.user?.name }}
          <RoleBadge :role="auth.role" />
          <a-button type="link" size="small" @click="logout">退出</a-button>
        </span>
      </a-layout-header>
      <a-layout-content style="margin:24px;background:#fff;padding:24px;border-radius:6px">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>
