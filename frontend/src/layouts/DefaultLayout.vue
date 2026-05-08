<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import AModal from 'ant-design-vue/es/modal';
import AInput from 'ant-design-vue/es/input';
import message from 'ant-design-vue/es/message';
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
    // v0.14-D: 归档项目不进 sidebar 4 条；先 filter 再排序
    myProjects.value = list
      .filter((p) => !p.archived)
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

const STATUS_LABEL: Record<ProjectStatus, string> = {
  drafting: '草稿', researching: '挖掘中', reporting: '检索完成', completed: '已完成',
};

/** v0.12-A: 4 段点状进度（drafting=1/4, researching=2/4, reporting=3/4, completed=4/4） */
function stageDots(s: ProjectStatus): boolean[] {
  const lvl = { drafting: 1, researching: 2, reporting: 3, completed: 4 }[s] ?? 0;
  return [0, 1, 2, 3].map(i => i < lvl);
}

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

/** v0.13-B: 项目右键菜单 — 重命名 / 归档 / 删除 */
function renameProject(p: Project) {
  const newTitle = ref(p.title);
  AModal.confirm({
    title: '重命名项目',
    icon: null,
    content: () => h(AInput, {
      value: newTitle.value,
      'onUpdate:value': (v: string) => { newTitle.value = v; },
      placeholder: '请输入新的项目标题',
      maxlength: 256,
    }),
    okText: '确定',
    cancelText: '取消',
    async onOk() {
      const t = (newTitle.value || '').trim();
      if (!t) {
        message.warning('标题不能为空');
        return Promise.reject();
      }
      if (t === p.title) return;
      try {
        await projectsApi.update(p.id, { title: t });
        message.success('已重命名');
        await loadMyProjects();
      } catch (e: any) {
        message.error('重命名失败：' + (e?.message || e));
      }
    },
  });
}

function toggleArchive(p: Project) {
  const willArchive = !p.archived;
  AModal.confirm({
    title: willArchive ? '归档此项目？' : '取消归档？',
    content: willArchive
      ? `项目 "${p.title}" 将被归档（仍可恢复）。`
      : `项目 "${p.title}" 将恢复到活跃列表。`,
    okText: '确定', cancelText: '取消',
    async onOk() {
      try {
        await projectsApi.update(p.id, { archived: willArchive });
        message.success(willArchive ? '已归档' : '已取消归档');
        await loadMyProjects();
      } catch (e: any) {
        message.error('操作失败：' + (e?.message || e));
      }
    },
  });
}

function deleteProject(p: Project) {
  AModal.confirm({
    title: `删除项目 "${p.title}"？`,
    content: '将连同其所有文件一并删除，无法恢复。',
    okText: '删除', okType: 'danger', cancelText: '取消',
    async onOk() {
      try {
        await projectsApi.remove(p.id);
        message.success('项目已删除');
        // 若当前正在被删的项目工作台内，回到 dashboard
        if (currentProjectId.value === p.id) {
          router.push('/employee/dashboard');
        }
        await loadMyProjects();
      } catch (e: any) {
        message.error('删除失败：' + (e?.message || e));
      }
    },
  });
}

/** v0.14-A: 抽出菜单点击处理，contextmenu 和 ⋯ click 复用 */
function onProjectMenuClick(p: Project, e: any) {
  e?.domEvent?.stopPropagation?.();
  if (e.key === 'rename') renameProject(p);
  else if (e.key === 'archive') toggleArchive(p);
  else if (e.key === 'delete') deleteProject(p);
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
              <a-dropdown v-for="p in myProjects" :key="p.id" :trigger="['contextmenu']">
                <div class="pp-proj-item"
                     :class="{ 'pp-proj-active': currentProjectId === p.id, 'pp-proj-archived': p.archived }"
                     @click="goProject(p)">
                  <!-- v0.14-A: hover 显示 ⋯ 三点菜单按钮，click 触发同一菜单 -->
                  <a-dropdown :trigger="['click']">
                    <a-button
                      type="text"
                      size="small"
                      class="pp-proj-actions"
                      title="更多操作"
                      @click.stop>⋯</a-button>
                    <template #overlay>
                      <a-menu @click="(e: any) => onProjectMenuClick(p, e)">
                        <a-menu-item key="rename">✏️ 重命名</a-menu-item>
                        <a-menu-item key="archive">
                          {{ p.archived ? '📤 取消归档' : '📦 归档' }}
                        </a-menu-item>
                        <a-menu-divider />
                        <a-menu-item key="delete" danger>🗑️ 删除</a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                  <div class="pp-proj-title">
                    <span v-if="p.archived" class="pp-archived-tag" title="已归档">📦</span>
                    {{ p.title }}
                  </div>
                  <div class="pp-proj-meta">
                    <!-- v0.12-A: 4 段进度徽章（报门→挖掘→检索→完成） -->
                    <span class="pp-stage" :title="STATUS_LABEL[p.status]">
                      <span v-for="(filled, i) in stageDots(p.status)" :key="i"
                            class="pp-dot" :class="{ on: filled }" />
                    </span>
                    <a-tag :color="STATUS_COLOR[p.status]" style="margin:0 0 0 6px;font-size:11px">
                      {{ STATUS_LABEL[p.status] }}
                    </a-tag>
                  </div>
                </div>
                <template #overlay>
                  <a-menu @click="(e: any) => onProjectMenuClick(p, e)">
                    <a-menu-item key="rename">✏️ 重命名</a-menu-item>
                    <a-menu-item key="archive">
                      {{ p.archived ? '📤 取消归档' : '📦 归档' }}
                    </a-menu-item>
                    <a-menu-divider />
                    <a-menu-item key="delete" danger>🗑️ 删除</a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
            </div>
          </a-spin>
          <a-button type="primary" block size="small" style="margin-top:8px" @click="newProject">
            ✨ 新建报门（登记新创意）
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
  position: relative;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.15s;
}
.pp-proj-item:hover {
  background: #f5f8ff;
}
/* v0.14-A: ⋯ 按钮 hover 时显示 */
.pp-proj-actions {
  position: absolute;
  top: 6px;
  right: 6px;
  opacity: 0;
  transition: opacity 0.15s;
  padding: 0 6px !important;
  height: 20px !important;
  line-height: 18px !important;
  font-size: 16px !important;
  color: #666;
  z-index: 1;
}
.pp-proj-item:hover .pp-proj-actions {
  opacity: 1;
}
.pp-proj-actions:hover {
  background: rgba(0, 0, 0, 0.06) !important;
  color: #1677ff;
}
@media (hover: none) {
  .pp-proj-actions {
    opacity: 1;
  }
}
.pp-proj-active {
  background: #e6f0ff;
  border-color: #91caff;
}
.pp-proj-archived {
  opacity: 0.55;
  background: #fafafa;
}
.pp-proj-archived .pp-proj-title {
  text-decoration: line-through;
  text-decoration-color: #bbb;
}
.pp-archived-tag {
  margin-right: 4px;
}
/* v0.12-A: 阶段点 */
.pp-stage {
  display: inline-flex;
  gap: 3px;
  vertical-align: middle;
}
.pp-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #d9d9d9;
  display: inline-block;
}
.pp-dot.on {
  background: #1677ff;
  box-shadow: 0 0 4px rgba(22, 119, 255, 0.4);
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
