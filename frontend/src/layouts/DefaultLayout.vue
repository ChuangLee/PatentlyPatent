<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useUIStore } from '@/stores/ui';
import { useFilesStore } from '@/stores/files';
import { projectsApi } from '@/api/projects';
import RoleBadge from '@/components/common/RoleBadge.vue';
import FileTree from '@/components/workbench/FileTree.vue';
import type { Project, ProjectStatus } from '@/types';

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const ui = useUIStore();
const filesStore = useFilesStore();

// 员工：sidebar 上半 = 我的项目（最多 4 个）；下半 = 当前项目文件树
const myProjects = ref<Project[]>([]);
const loadingProjects = ref(false);

async function loadMyProjects() {
  if (auth.role !== 'employee' || !auth.user) return;
  loadingProjects.value = true;
  try {
    const list = await projectsApi.list({ ownerId: auth.user.id });
    // 按 updatedAt desc 排，取前 4
    myProjects.value = [...list]
      .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))
      .slice(0, 4);
  } finally {
    loadingProjects.value = false;
  }
}

onMounted(loadMyProjects);
watch(() => route.fullPath, loadMyProjects);  // 路由变更时刷新（新建项目后回到 dashboard）

const STATUS_COLOR: Record<ProjectStatus, string> = {
  drafting: 'default',
  researching: 'processing',
  reporting: 'cyan',
  completed: 'success',
};

// 当前路由是否在某项目工作台内（决定是否高亮文件树/隐藏空态）
const currentProjectId = computed(() => {
  const m = route.path.match(/\/projects\/([^/]+)\//);
  return m ? m[1] : null;
});

function goProject(p: Project) {
  router.push(`/employee/projects/${p.id}/workbench`);
}

function goAllProjects() {
  router.push('/employee/dashboard');
}

function newProject() {
  router.push('/employee/dashboard?new=1');
}

function logout() {
  auth.logout();
  router.push('/login');
}

// admin 仍用菜单
interface MenuItem { key: string; label: string; icon?: string; disabled?: boolean }
const adminMenuItems = computed<MenuItem[]>(() => [
  { key: '/admin/dashboard', label: '总览', icon: '📊' },
  { key: '/admin/projects', label: '全量项目', icon: '📋' },
  { key: 'sep', label: '— 浏览员工视图 —', disabled: true },
  { key: '/employee/dashboard', label: '员工工作台', icon: '👤' },
]);
const selectedKeys = computed(() => [route.path]);
function onMenuClick({ key }: { key: string }) {
  if (key !== 'sep') router.push(key);
}
</script>

<template>
  <a-layout style="min-height:100vh">
    <a-layout-sider :collapsed="ui.sidebarCollapsed" collapsible
                    :width="280"
                    @update:collapsed="ui.toggleSidebar()" theme="light"
                    style="display:flex;flex-direction:column">
      <div class="pp-brand">
        <strong>PatentlyPatent</strong>
      </div>

      <!-- 员工 sidebar：上半项目列表 + 下半文件树 -->
      <div v-if="auth.role === 'employee'" class="pp-sider-employee">
        <!-- 上半：我的项目（紧凑，最多 4） -->
        <div class="pp-sec">
          <div class="pp-sec-head">
            <span>我的项目</span>
            <a-tooltip title="查看全部"><a-button type="link" size="small" @click="goAllProjects">全部 →</a-button></a-tooltip>
          </div>
          <a-spin :spinning="loadingProjects" size="small">
            <div v-if="!loadingProjects && myProjects.length === 0" class="pp-empty">还没有项目</div>
            <div v-else class="pp-proj-list">
              <div v-for="p in myProjects" :key="p.id"
                   class="pp-proj-item"
                   :class="{ 'pp-proj-active': currentProjectId === p.id }"
                   @click="goProject(p)">
                <div class="pp-proj-title">{{ p.title }}</div>
                <div class="pp-proj-meta">
                  <a-tag :color="STATUS_COLOR[p.status]" style="margin:0">{{ p.domain }}</a-tag>
                </div>
              </div>
            </div>
          </a-spin>
          <a-button type="primary" block size="small" style="margin-top:8px" @click="newProject">
            ✨ 新建报门
          </a-button>
        </div>

        <a-divider style="margin:8px 0" />

        <!-- 下半：当前项目文件树 -->
        <div class="pp-sec pp-sec-grow">
          <div class="pp-sec-head">
            <span>📁 项目文件</span>
            <span v-if="!currentProjectId" style="color:#aaa;font-size:12px">未选项目</span>
          </div>
          <div v-if="!currentProjectId" class="pp-empty">在上方选一个项目以查看文件</div>
          <FileTree v-else :project-id="currentProjectId" />
        </div>
      </div>

      <!-- admin sidebar：传统菜单 -->
      <a-menu v-else :selected-keys="selectedKeys" mode="inline" @click="onMenuClick">
        <template v-for="item in adminMenuItems" :key="item.key">
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

<style scoped>
.pp-brand {
  padding: 16px;
  text-align: center;
  border-bottom: 1px solid #eee;
}
.pp-sider-employee {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);   /* 减去 brand 高度 */
  overflow: hidden;
}
.pp-sec {
  padding: 8px 12px;
}
.pp-sec-grow {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.pp-sec-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: 12px;
  color: #666;
  font-weight: 600;
}
.pp-empty {
  padding: 16px 0;
  text-align: center;
  color: #aaa;
  font-size: 12px;
}
.pp-proj-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 220px;     /* 卡 4 项左右 */
  overflow: auto;
}
.pp-proj-item {
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.15s;
}
.pp-proj-item:hover {
  background: #f5f8ff;
}
.pp-proj-active {
  background: #e6f0ff;
  border-color: #91caff;
}
.pp-proj-title {
  font-size: 13px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.pp-proj-meta {
  margin-top: 4px;
}
</style>
