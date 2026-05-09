<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import AModal from 'ant-design-vue/es/modal';
import AInput from 'ant-design-vue/es/input';
import message from 'ant-design-vue/es/message';
import { useAuthStore } from '@/stores/auth';
import { useUIStore } from '@/stores/ui';
import { projectsApi } from '@/api/projects';
import RoleBadge from '@/components/common/RoleBadge.vue';
import FileTree from '@/components/workbench/FileTree.vue';
import UsageTutorial from '@/components/tutorial/UsageTutorial.vue';
import type { Project, ProjectStatus } from '@/types';

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const ui = useUIStore();

// 员工：sidebar 上半 = 我的项目（最多 4 个）；下半 = 当前项目文件树
const myProjects = ref<Project[]>([]);
const loadingProjects = ref(false);

async function loadMyProjects() {
  if (auth.role !== 'employee' || !auth.user) return;
  loadingProjects.value = true;
  try {
    const list = await projectsApi.list({ ownerId: auth.user.id });
    myProjects.value = list
      .filter((p) => !p.archived)
      .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))
      .slice(0, 4);
  } finally {
    loadingProjects.value = false;
  }
}

onMounted(loadMyProjects);
watch(() => route.fullPath, loadMyProjects);

const STATUS_COLOR: Record<ProjectStatus, string> = {
  drafting: 'default',
  researching: 'processing',
  reporting: 'cyan',
  completed: 'success',
};

const STATUS_LABEL: Record<ProjectStatus, string> = {
  drafting: '草稿', researching: '挖掘中', reporting: '检索完成', completed: '已完成',
};

function stageDots(s: ProjectStatus): boolean[] {
  const lvl = { drafting: 1, researching: 2, reporting: 3, completed: 4 }[s] ?? 0;
  return [0, 1, 2, 3].map(i => i < lvl);
}

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

// Header 当前页面标题
const currentTitle = computed(() => (route.meta?.title as string) || '');

// 面包屑：基于 route.path 与已加载的 myProjects 动态生成
interface Crumb { label: string; path?: string }
const HOME_PATH = computed(() => (auth.role === 'admin' ? '/admin/dashboard' : '/employee/dashboard'));

const breadcrumbs = computed<Crumb[]>(() => {
  const path = route.path;
  // dashboard 自身：仅显示「首页」（最后一段）
  if (path.startsWith('/employee/dashboard') || path.startsWith('/admin/dashboard')) {
    return [{ label: '首页' }];
  }
  const list: Crumb[] = [{ label: '首页', path: HOME_PATH.value }];
  if (path.startsWith('/employee/projects')) {
    list.push({ label: '项目', path: '/employee/dashboard' });
    if (currentProjectId.value) {
      const p = myProjects.value.find(x => x.id === currentProjectId.value);
      list.push({ label: p?.title || '项目详情' });
    } else if (path.includes('/projects/new')) {
      list.push({ label: '新建项目' });
    }
    return list;
  }
  if (path.startsWith('/admin/projects')) {
    list.push({ label: '全量项目' });
    return list;
  }
  if (currentTitle.value) list.push({ label: currentTitle.value });
  return list;
});

function goCrumb(c: Crumb) {
  if (c.path) router.push(c.path);
}

// 用户首字母 avatar
const avatarLetter = computed(() => {
  const n = auth.user?.name || '';
  return n ? n.slice(0, 1).toUpperCase() : '?';
});

const userDept = computed(() => auth.user?.department || '');

// 装饰性搜索框（暂不接逻辑）
const searchValue = ref('');

const APP_VERSION = 'v0.26';

// v0.26：使用教程 modal
const tutorialOpen = ref(false);
function openTutorial() { tutorialOpen.value = true; }
function closeTutorial() { tutorialOpen.value = false; }
function tutorialStartNow() {
  tutorialOpen.value = false;
  router.push('/employee/dashboard?new=1');
}
</script>

<template>
  <a-layout class="pp-shell">
    <!-- ================= Sidebar ================= -->
    <a-layout-sider
      :collapsed="ui.sidebarCollapsed"
      collapsible
      :width="260"
      :collapsed-width="64"
      :trigger="null"
      theme="light"
      class="pp-sider"
    >
      <!-- 顶部 brand + 折叠按钮 -->
      <div class="pp-sider__brand">
        <a class="pp-sider__brand-link" @click="router.push(auth.role === 'admin' ? '/admin/dashboard' : '/employee/dashboard')">
          <span class="pp-sider__logo">PP</span>
          <span v-if="!ui.sidebarCollapsed" class="pp-sider__brand-text">PatentlyPatent</span>
        </a>
        <button
          type="button"
          class="pp-sider__collapse"
          :title="ui.sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
          @click="ui.toggleSidebar()"
        >
          <span>{{ ui.sidebarCollapsed ? '»' : '«' }}</span>
        </button>
      </div>

      <!-- 用户卡片 -->
      <div v-if="!ui.sidebarCollapsed && auth.user" class="pp-sider__user">
        <div class="pp-sider__avatar">{{ avatarLetter }}</div>
        <div class="pp-sider__user-meta">
          <div class="pp-sider__user-name">{{ auth.user.name }}</div>
          <div class="pp-sider__user-sub">
            {{ auth.role === 'admin' ? '管理员' : '员工' }}
            <span v-if="userDept">· {{ userDept }}</span>
          </div>
        </div>
      </div>

      <!-- 员工 sidebar -->
      <div v-if="auth.role === 'employee'" class="pp-sider__body">
        <div class="pp-sec">
          <div class="pp-sec-head">
            <span>我的项目</span>
            <a-button type="link" size="small" class="pp-sec-link" @click="goAllProjects">全部 →</a-button>
          </div>
          <a-spin :spinning="loadingProjects" size="small">
            <div v-if="!loadingProjects && myProjects.length === 0" class="pp-empty">还没有项目</div>
            <div v-else class="pp-proj-list">
              <a-dropdown v-for="p in myProjects" :key="p.id" :trigger="['contextmenu']">
                <div
                  class="pp-proj-item"
                  :class="{ 'pp-proj-active': currentProjectId === p.id, 'pp-proj-archived': p.archived }"
                  @click="goProject(p)"
                >
                  <span v-if="currentProjectId === p.id" class="pp-proj-rail" aria-hidden="true" />
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
                    <span class="pp-stage" :title="STATUS_LABEL[p.status]">
                      <span v-for="(filled, i) in stageDots(p.status)" :key="i"
                            class="pp-dot" :class="{ on: filled }" />
                    </span>
                    <a-tag :color="STATUS_COLOR[p.status]" class="pp-proj-status-tag">
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
          <a-button
            type="primary"
            block
            size="small"
            class="pp-newproj-btn"
            @click="newProject"
          >
            ✨ 新建报门
          </a-button>
        </div>

        <div class="pp-sec-divider" />

        <div class="pp-sec pp-sec-grow">
          <div class="pp-sec-head">
            <span>📁 项目文件</span>
            <span v-if="!currentProjectId" class="pp-sec-tip">未选项目</span>
          </div>
          <div v-if="!currentProjectId" class="pp-empty">在上方选一个项目以查看文件</div>
          <FileTree v-else :project-id="currentProjectId" />
        </div>
      </div>

      <!-- admin sidebar -->
      <a-menu
        v-else
        :selected-keys="selectedKeys"
        mode="inline"
        class="pp-admin-menu"
        @click="onMenuClick"
      >
        <template v-for="item in adminMenuItems" :key="item.key">
          <a-menu-item v-if="!item.disabled" :key="item.key">
            <span>{{ item.icon }} {{ item.label }}</span>
          </a-menu-item>
          <a-menu-divider v-else />
        </template>
      </a-menu>

      <!-- 版本号 -->
      <div v-if="!ui.sidebarCollapsed" class="pp-sider__foot">
        PatentlyPatent · {{ APP_VERSION }}
      </div>
    </a-layout-sider>

    <a-layout class="pp-main">
      <!-- ================= Header ================= -->
      <a-layout-header class="pp-header">
        <div class="pp-header__left">
          <span class="pp-header__brand-mini">
            <span class="pp-header__brand-dot" />
            <strong>PatentlyPatent</strong>
          </span>
          <span v-if="currentTitle" class="pp-header__sep">›</span>
          <span v-if="currentTitle" class="pp-header__page">{{ currentTitle }}</span>
          <nav v-if="breadcrumbs.length > 0" class="pp-crumbs" aria-label="breadcrumb">
            <template v-for="(c, i) in breadcrumbs" :key="i">
              <span v-if="i > 0" class="pp-crumbs__sep">›</span>
              <a
                v-if="c.path && i !== breadcrumbs.length - 1"
                class="pp-crumbs__item pp-crumbs__link"
                @click="goCrumb(c)"
              >{{ c.label }}</a>
              <span
                v-else
                class="pp-crumbs__item pp-crumbs__current"
              >{{ c.label }}</span>
            </template>
          </nav>
        </div>

        <div class="pp-header__right">
          <div class="pp-header__search">
            <span class="pp-header__search-icon">🔍</span>
            <input
              v-model="searchValue"
              class="pp-header__search-input"
              placeholder="搜项目 / 知识 / 命令..."
            />
            <span class="pp-header__search-kbd">⌘K</span>
          </div>

          <button
            class="pp-header__tutorial-btn"
            title="使用教程"
            data-testid="tutorial-btn"
            @click="openTutorial"
          >
            📖 使用教程
          </button>

          <button
            class="pp-header__icon-btn"
            :title="ui.theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'"
            @click="ui.toggleTheme()"
          >
            {{ ui.theme === 'dark' ? '☀️' : '🌙' }}
          </button>

          <button class="pp-header__icon-btn" title="通知">
            🔔
            <span class="pp-header__badge" />
          </button>

          <div class="pp-header__user">
            <div class="pp-header__avatar">{{ avatarLetter }}</div>
            <div class="pp-header__user-text">
              <div class="pp-header__user-name">{{ auth.user?.name }}</div>
              <RoleBadge :role="auth.role" />
            </div>
          </div>

          <a-button type="text" size="small" class="pp-header__logout" @click="logout">退出</a-button>
        </div>
      </a-layout-header>

      <a-layout-content class="pp-content">
        <router-view />
      </a-layout-content>
    </a-layout>

    <!-- v0.26：使用教程 modal -->
    <a-modal
      :open="tutorialOpen"
      :width="1200"
      :style="{ top: '40px' }"
      :footer="null"
      :body-style="{ padding: 0, maxHeight: '78vh', overflowY: 'auto' }"
      :destroy-on-close="true"
      wrap-class-name="pp-tutorial-modal"
      title="📖 PatentlyPatent 使用教程"
      @cancel="closeTutorial"
      @update:open="(v: boolean) => (tutorialOpen = v)"
    >
      <UsageTutorial @start="tutorialStartNow" @skip="closeTutorial" />
    </a-modal>
  </a-layout>
</template>

<style scoped>
.pp-shell {
  min-height: 100vh;
  background: var(--pp-color-bg);
}

/* ================= Sidebar ================= */
.pp-sider {
  background: var(--pp-color-surface) !important;
  border-right: 1px solid var(--pp-color-border-soft);
  display: flex;
  flex-direction: column;
  position: relative;
}
.pp-sider :deep(.ant-layout-sider-children) {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.pp-sider__brand {
  height: var(--pp-header-h, 56px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid var(--pp-color-border-soft);
}
.pp-sider__brand-link {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  color: var(--pp-color-text);
  text-decoration: none;
  flex: 1;
  min-width: 0;
}
.pp-sider__logo {
  width: 32px;
  height: 32px;
  border-radius: var(--pp-radius-md);
  background: linear-gradient(135deg, #5B6CFF 0%, #8B5CF6 100%);
  color: #fff;
  font-weight: 700;
  font-size: 13px;
  letter-spacing: 0.5px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(91, 108, 255, 0.28);
}
.pp-sider__brand-text {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pp-sider__collapse {
  border: none;
  background: transparent;
  color: var(--pp-color-text-tertiary);
  cursor: pointer;
  width: 24px;
  height: 24px;
  border-radius: var(--pp-radius-sm);
  font-size: 14px;
  flex-shrink: 0;
}
.pp-sider__collapse:hover {
  background: var(--pp-color-bg-elevated);
  color: var(--pp-color-text);
}

.pp-sider__user {
  margin: var(--pp-space-3);
  padding: 10px 12px;
  border-radius: var(--pp-radius-md);
  background: var(--pp-color-bg-elevated);
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--pp-color-border-soft);
}
.pp-sider__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #5B6CFF 0%, #8B5CF6 100%);
  color: #fff;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  flex-shrink: 0;
}
.pp-sider__user-meta { min-width: 0; flex: 1; }
.pp-sider__user-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--pp-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pp-sider__user-sub {
  font-size: 11px;
  color: var(--pp-color-text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pp-sider__body {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.pp-sec {
  padding: var(--pp-space-3);
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
  padding: 4px 0 8px;
  font-size: 11px;
  color: var(--pp-color-text-tertiary);
  font-weight: 600;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}
.pp-sec-link { padding: 0; height: auto; font-size: 11px; }
.pp-sec-tip { color: var(--pp-color-text-tertiary); font-size: 11px; }
.pp-sec-divider {
  height: 1px;
  background: var(--pp-color-border-soft);
  margin: 4px var(--pp-space-3);
}

.pp-empty {
  padding: 16px 0;
  text-align: center;
  color: var(--pp-color-text-tertiary);
  font-size: 12px;
}
.pp-proj-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 240px;
  overflow: auto;
}
.pp-proj-item {
  position: relative;
  /* v0.34.2 fix: 右 padding 留 32px 给绝对定位的「⋯」按钮，避免标题文字被覆盖 */
  padding: 8px 32px 8px 14px;
  border-radius: var(--pp-radius-md);
  cursor: pointer;
  border: 1px solid transparent;
  transition: var(--pp-transition);
  background: transparent;
}
.pp-proj-item:hover {
  background: var(--pp-color-primary-soft);
}
.pp-proj-rail {
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 4px;
  border-radius: 2px;
  background: var(--pp-color-primary);
}
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
  color: var(--pp-color-text-tertiary);
  z-index: 1;
}
.pp-proj-item:hover .pp-proj-actions {
  opacity: 1;
}
.pp-proj-actions:hover {
  background: rgba(0, 0, 0, 0.06) !important;
  color: var(--pp-color-primary);
}
@media (hover: none) {
  .pp-proj-actions { opacity: 1; }
}
.pp-proj-active {
  background: var(--pp-color-primary-soft);
}
.pp-proj-active .pp-proj-title {
  color: var(--pp-color-primary);
  font-weight: 600;
}
.pp-proj-archived {
  opacity: 0.55;
  background: var(--pp-color-bg-elevated);
}
.pp-proj-archived .pp-proj-title {
  text-decoration: line-through;
  text-decoration-color: var(--pp-color-text-tertiary);
}
.pp-archived-tag { margin-right: 4px; }

.pp-stage { display: inline-flex; gap: 3px; vertical-align: middle; }
.pp-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--pp-color-border);
  display: inline-block;
}
.pp-dot.on {
  background: var(--pp-color-primary);
  box-shadow: 0 0 4px rgba(91, 108, 255, 0.4);
}
.pp-proj-title {
  font-size: 13px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  color: var(--pp-color-text);
}
.pp-proj-meta { margin-top: 6px; }
.pp-proj-status-tag {
  margin: 0 0 0 6px !important;
  font-size: 11px !important;
}
.pp-newproj-btn {
  margin-top: var(--pp-space-3);
  height: 36px;
  border-radius: var(--pp-radius-md);
  font-weight: 500;
}

.pp-admin-menu {
  border-right: none !important;
  padding: var(--pp-space-3);
  background: transparent !important;
}

.pp-sider__foot {
  padding: 10px var(--pp-space-3);
  font-size: 11px;
  color: var(--pp-color-text-tertiary);
  text-align: center;
  border-top: 1px solid var(--pp-color-border-soft);
  letter-spacing: 0.3px;
}

/* ================= Header ================= */
.pp-main { background: var(--pp-color-bg); }
.pp-header {
  height: var(--pp-header-h, 56px);
  line-height: normal;
  background: var(--pp-color-surface) !important;
  border-bottom: 1px solid var(--pp-color-border-soft);
  padding: 0 var(--pp-space-5) !important;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--pp-space-4);
}
.pp-header__left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.pp-header__brand-mini {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--pp-color-text);
  letter-spacing: 0.2px;
}
.pp-header__brand-dot {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, #5B6CFF 0%, #8B5CF6 60%, #EC4899 100%);
  display: inline-block;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(91, 108, 255, 0.32);
}
.pp-header__sep {
  color: var(--pp-color-text-tertiary);
  font-size: 14px;
}
.pp-header__page {
  color: var(--pp-color-text-secondary);
  font-size: 13px;
  font-weight: 500;
}

/* ---------- 面包屑 ---------- */
.pp-crumbs {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: 6px;
  font-size: 12px;
  color: var(--pp-color-text-tertiary);
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.pp-crumbs__sep {
  color: var(--pp-color-text-tertiary);
  user-select: none;
}
.pp-crumbs__item {
  display: inline-block;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}
.pp-crumbs__link {
  color: var(--pp-color-text-tertiary);
  cursor: pointer;
  transition: color var(--pp-transition-fast);
}
.pp-crumbs__link:hover {
  color: var(--pp-color-primary);
}
.pp-crumbs__current {
  color: var(--pp-color-text-secondary);
  font-weight: 500;
  cursor: default;
}

.pp-header__right {
  display: flex;
  align-items: center;
  gap: var(--pp-space-3);
}

.pp-header__search {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 10px;
  border-radius: var(--pp-radius-md);
  background: var(--pp-color-bg-elevated);
  border: 1px solid transparent;
  width: 220px;
  transition: var(--pp-transition);
}
.pp-header__search:focus-within {
  background: var(--pp-color-surface);
  border-color: var(--pp-color-primary);
  box-shadow: var(--pp-shadow-focus);
}
.pp-header__search-icon { font-size: 13px; color: var(--pp-color-text-tertiary); }
.pp-header__search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--pp-color-text);
  font-family: inherit;
  min-width: 0;
}
.pp-header__search-input::placeholder { color: var(--pp-color-text-tertiary); }
.pp-header__search-kbd {
  font-size: 10px;
  color: var(--pp-color-text-tertiary);
  border: 1px solid var(--pp-color-border);
  border-radius: 4px;
  padding: 1px 5px;
  background: var(--pp-color-surface);
  letter-spacing: 0.5px;
}

.pp-header__tutorial-btn {
  height: 32px;
  padding: 0 12px;
  border-radius: var(--pp-radius-md);
  border: 1px solid var(--pp-color-border);
  background: var(--pp-color-bg-elevated);
  color: var(--pp-color-text-secondary);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  letter-spacing: 0.2px;
  transition: var(--pp-transition);
}
.pp-header__tutorial-btn:hover {
  border-color: var(--pp-color-primary);
  color: var(--pp-color-primary);
  background: var(--pp-color-surface);
  box-shadow: var(--pp-shadow-sm);
}
@media (max-width: 900px) {
  .pp-header__tutorial-btn {
    padding: 0 8px;
    font-size: 12px;
  }
}

.pp-header__icon-btn {
  position: relative;
  width: 32px;
  height: 32px;
  border-radius: var(--pp-radius-md);
  border: none;
  background: transparent;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: var(--pp-color-text-secondary);
  transition: var(--pp-transition);
}
.pp-header__icon-btn:hover {
  background: var(--pp-color-bg-elevated);
  color: var(--pp-color-text);
}
.pp-header__badge {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--pp-color-danger);
  border: 1.5px solid var(--pp-color-surface);
}

.pp-header__user {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px 4px 4px;
  border-radius: var(--pp-radius-full);
  background: var(--pp-color-bg-elevated);
}
.pp-header__avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #5B6CFF 0%, #8B5CF6 100%);
  color: #fff;
  font-weight: 600;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.pp-header__user-text { display: flex; align-items: center; gap: 2px; }
.pp-header__user-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--pp-color-text);
}
.pp-header__logout { color: var(--pp-color-text-secondary); }

/* ================= Content ================= */
.pp-content {
  margin: var(--pp-space-5);
  padding: var(--pp-space-5) var(--pp-space-6);
  background: transparent;
  border-radius: 0;
  min-height: calc(100vh - var(--pp-header-h, 56px) - 40px);
}

/* ================= 响应式 ================= */
@media (max-width: 900px) {
  .pp-header__search { display: none; }
  .pp-header__user-text { display: none; }
  .pp-content { margin: var(--pp-space-3); padding: var(--pp-space-4); }
}
</style>
