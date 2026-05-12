<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { useAuthStore } from '@/stores/auth';
import NewProjectModal from '@/components/workbench/NewProjectModal.vue';
import AModal from 'ant-design-vue/es/modal';
import message from 'ant-design-vue/es/message';
import type { Project, ProjectStatus } from '@/types';

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const projects = ref<Project[]>([]);
const loading = ref(true);
const modalOpen = ref(false);

// v0.14-D: 活跃 / 已归档 切换，默认活跃
const archivedFilter = ref<'活跃' | '已归档'>('活跃');
const filteredProjects = computed(() =>
  projects.value.filter((p) =>
    archivedFilter.value === '已归档' ? p.archived === true : p.archived !== true,
  ),
);

async function refresh() {
  loading.value = true;
  projects.value = await projectsApi.list({ ownerId: auth.user!.id });
  loading.value = false;
}

onMounted(() => {
  refresh();
  if (route.query.new === '1') {
    modalOpen.value = true;
    router.replace({ path: route.path, query: {} });
  }
});

watch(() => route.query.new, (v) => {
  if (v === '1') {
    modalOpen.value = true;
    router.replace({ path: route.path, query: {} });
  }
});

const STATUS_LABEL: Record<ProjectStatus, { text: string; color: string }> = {
  drafting:    { text: '草稿', color: 'default' },
  researching: { text: '挖掘中', color: 'processing' },
  reporting:   { text: '检索完成', color: 'cyan' },
  completed:   { text: '已完成', color: 'success' },
};

const DOMAIN_LABEL: Record<string, string> = {
  cryptography: '密码学',
  infosec: '信息安全',
  ai: '人工智能',
  other: '通用',
};

/** v0.12-A: 4 段进度点 */
function stageDots(s: ProjectStatus): boolean[] {
  const lvl = { drafting: 1, researching: 2, reporting: 3, completed: 4 }[s] ?? 0;
  return [0, 1, 2, 3].map(i => i < lvl);
}

const STAGE_NAMES = ['报门', '挖掘', '检索', '完成'];

// 顶部统计
const stats = computed(() => {
  const active = projects.value.filter(p => !p.archived);
  const inProgress = active.filter(p => p.status !== 'completed').length;
  const done = active.filter(p => p.status === 'completed').length;
  // 本周更新 (近 7 天 updatedAt)
  const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
  const weekActive = active.filter(p => +new Date(p.updatedAt) >= weekAgo).length;
  return { inProgress, done, weekActive };
});

function go(p: Project) {
  router.push(`/employee/projects/${p.id}/workbench`);
}

// v0.37: 多选 + 批量删除
const selectMode = ref(false);
const selected = ref<Set<string>>(new Set());
function toggleSelectMode() {
  selectMode.value = !selectMode.value;
  if (!selectMode.value) selected.value = new Set();
}
function toggleSelect(p: Project, ev: MouseEvent) {
  ev.stopPropagation();
  const s = new Set(selected.value);
  if (s.has(p.id)) s.delete(p.id); else s.add(p.id);
  selected.value = s;
}
function selectAll() {
  selected.value = new Set(filteredProjects.value.map(p => p.id));
}
function clearSelection() { selected.value = new Set(); }
async function deleteSelected() {
  const ids = [...selected.value];
  if (ids.length === 0) {
    message.warning('请先勾选要删除的项目');
    return;
  }
  AModal.confirm({
    title: `确认删除 ${ids.length} 个项目？`,
    content: '项目及其文件树、对话历史、AI 输出都会删除，无法恢复。',
    okText: '删除', okType: 'danger', cancelText: '取消',
    async onOk() {
      let ok = 0, fail = 0;
      for (const id of ids) {
        try { await projectsApi.remove(id); ok++; }
        catch (e: any) { fail++; console.warn('delete', id, e?.message); }
      }
      message.success(`已删除 ${ok}${fail ? `，失败 ${fail}` : ''}`);
      selected.value = new Set();
      selectMode.value = false;
      refresh();
    },
  });
}

// v0.37: 单卡 ⋯ 菜单
async function archiveProject(p: Project, ev?: Event) {
  ev?.stopPropagation();
  try {
    await projectsApi.update(p.id, { archived: !p.archived });
    message.success(p.archived ? '已取消归档' : '已归档');
    refresh();
  } catch (e: any) { message.error('操作失败：' + (e?.message || e)); }
}
function deleteOne(p: Project, ev?: Event) {
  ev?.stopPropagation();
  AModal.confirm({
    title: `确认删除项目 "${p.title}"？`,
    content: '项目及其文件树、对话历史、AI 输出都会删除，无法恢复。',
    okText: '删除', okType: 'danger', cancelText: '取消',
    async onOk() {
      try {
        await projectsApi.remove(p.id);
        message.success('已删除');
        refresh();
      } catch (e: any) { message.error('删除失败：' + (e?.message || e)); }
    },
  });
}
</script>

<template>
  <div class="pp-dash">
    <!-- 欢迎卡 -->
    <section class="pp-dash__welcome">
      <div class="pp-dash__welcome-text">
        <h1 class="pp-dash__hello">
          你好，<span class="pp-dash__name">{{ auth.user?.name || '同学' }}</span>
        </h1>
        <p class="pp-dash__sub">
          <template v-if="stats.inProgress > 0">
            今天有
            <strong class="pp-dash__sub-num">{{ stats.inProgress }}</strong>
            个项目正在挖掘中，AI agent 已就位
          </template>
          <template v-else>
            还没有进行中的项目，开始一个新的创意吧
          </template>
        </p>
      </div>
      <a-button
        type="primary"
        size="large"
        class="pp-dash__cta"
        @click="modalOpen = true"
      >
        ✨&nbsp; 新建报门
      </a-button>
    </section>

    <!-- 统计三栏 -->
    <section class="pp-dash__stats">
      <div class="pp-card pp-stat">
        <div class="pp-stat__label">进行中</div>
        <div class="pp-stat__value">{{ stats.inProgress }}</div>
        <div class="pp-stat__hint">需要你下一步推进</div>
        <span class="pp-stat__deco pp-stat__deco--primary" />
      </div>
      <div class="pp-card pp-stat">
        <div class="pp-stat__label">已完成</div>
        <div class="pp-stat__value">{{ stats.done }}</div>
        <div class="pp-stat__hint">已导出交底书</div>
        <span class="pp-stat__deco pp-stat__deco--success" />
      </div>
      <div class="pp-card pp-stat">
        <div class="pp-stat__label">本周活跃</div>
        <div class="pp-stat__value">{{ stats.weekActive }}</div>
        <div class="pp-stat__hint">近 7 天有更新</div>
        <span class="pp-stat__deco pp-stat__deco--pink" />
      </div>
    </section>

    <!-- 项目区 header -->
    <div class="pp-dash__list-head">
      <h2 class="pp-dash__list-title">我的创新项目</h2>
      <div class="pp-dash__list-actions">
        <template v-if="selectMode">
          <span class="pp-dash__sel-count">已选 {{ selected.size }} / {{ filteredProjects.length }}</span>
          <a-button size="small" @click="selectAll" :disabled="selected.size === filteredProjects.length">全选</a-button>
          <a-button size="small" @click="clearSelection" :disabled="selected.size === 0">清空</a-button>
          <a-button size="small" danger :disabled="selected.size === 0" @click="deleteSelected">🗑 删除选中</a-button>
          <a-button size="small" @click="toggleSelectMode">取消</a-button>
        </template>
        <template v-else>
          <a-button size="small" @click="toggleSelectMode">☐ 多选</a-button>
          <a-segmented v-model:value="archivedFilter" :options="['活跃', '已归档']" />
        </template>
      </div>
    </div>

    <a-spin :spinning="loading">
      <a-empty
        v-if="!loading && filteredProjects.length === 0"
        :description="archivedFilter === '已归档'
          ? '没有已归档的项目'
          : (projects.length === 0 ? `还没有项目，点 “新建报门” 开始` : '没有活跃项目')"
        style="padding:48px 0"
      />
      <div v-else class="pp-dash__grid">
        <article
          v-for="p in filteredProjects"
          :key="p.id"
          class="pp-pcard pp-card pp-card-hoverable"
          :class="{ 'pp-pcard--archived': p.archived, 'pp-pcard--selected': selected.has(p.id) }"
          @click="selectMode ? toggleSelect(p, $event) : go(p)"
        >
          <header class="pp-pcard__head">
            <input v-if="selectMode" type="checkbox"
                   class="pp-pcard__check"
                   :checked="selected.has(p.id)"
                   @click.stop="toggleSelect(p, $event)"
                   @change="(e) => e.stopPropagation()" />
            <h3 class="pp-pcard__title">{{ p.title }}</h3>
            <a-tag :color="STATUS_LABEL[p.status].color" class="pp-pcard__tag">
              {{ STATUS_LABEL[p.status].text }}
            </a-tag>
            <a-dropdown v-if="!selectMode" :trigger="['click']">
              <a class="pp-pcard__more" @click.stop.prevent>⋯</a>
              <template #overlay>
                <a-menu>
                  <a-menu-item key="archive" @click="(arg: any) => archiveProject(p, arg.domEvent)">
                    {{ p.archived ? '取消归档' : '归档' }}
                  </a-menu-item>
                  <a-menu-item key="delete" danger @click="(arg: any) => deleteOne(p, arg.domEvent)">
                    删除
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </header>

          <div class="pp-pcard__progress">
            <div
              v-for="(filled, i) in stageDots(p.status)"
              :key="i"
              class="pp-pcard__step"
              :class="{ 'pp-pcard__step--on': filled }"
            >
              <span class="pp-pcard__dot" />
              <span class="pp-pcard__step-label">{{ STAGE_NAMES[i] }}</span>
            </div>
          </div>

          <p class="pp-pcard__desc">{{ p.description || '暂无描述' }}</p>

          <footer class="pp-pcard__foot">
            <span class="pp-pcard__domain">
              {{ DOMAIN_LABEL[p.domain] || p.customDomain || p.domain }}
            </span>
            <span class="pp-pcard__open">打开 →</span>
          </footer>
        </article>
      </div>
    </a-spin>

    <NewProjectModal v-model:open="modalOpen" @created="refresh" />
  </div>
</template>

<style scoped>
.pp-dash {
  display: flex;
  flex-direction: column;
  gap: var(--pp-space-5);
}

/* ---------- 欢迎卡 ---------- */
.pp-dash__welcome {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--pp-space-4);
  padding: var(--pp-space-5) var(--pp-space-6);
  border-radius: var(--pp-radius-lg);
  background:
    linear-gradient(135deg, rgba(91, 108, 255, 0.10) 0%, rgba(139, 92, 246, 0.06) 50%, rgba(236, 72, 153, 0.06) 100%),
    var(--pp-color-surface);
  border: 1px solid var(--pp-color-border-soft);
  box-shadow: var(--pp-shadow-sm);
  flex-wrap: wrap;
}
.pp-dash__hello {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 4px;
  letter-spacing: -0.01em;
  color: var(--pp-color-text);
}
.pp-dash__name {
  background: linear-gradient(135deg, #5B6CFF 0%, #8B5CF6 60%, #EC4899 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.pp-dash__sub {
  margin: 0;
  font-size: 13px;
  color: var(--pp-color-text-secondary);
}
.pp-dash__sub-num {
  color: var(--pp-color-primary);
  font-weight: 700;
  margin: 0 2px;
}
.pp-dash__cta {
  height: 44px;
  border-radius: var(--pp-radius-md);
  font-weight: 600;
  letter-spacing: 0.3px;
  padding: 0 var(--pp-space-5);
  box-shadow: 0 6px 18px rgba(91, 108, 255, 0.28);
}

/* ---------- 统计三栏 ---------- */
.pp-dash__stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--pp-space-4);
}
.pp-stat {
  position: relative;
  padding: var(--pp-space-5);
  overflow: hidden;
}
.pp-stat__label {
  font-size: 13px;
  color: var(--pp-color-text-secondary);
  font-weight: 500;
  letter-spacing: 0.2px;
  margin-bottom: 8px;
}
.pp-stat__value {
  font-size: 32px;
  font-weight: 700;
  color: var(--pp-color-text);
  letter-spacing: -0.02em;
  line-height: 1.1;
}
.pp-stat__hint {
  font-size: 12px;
  color: var(--pp-color-text-tertiary);
  margin-top: 6px;
}
.pp-stat__deco {
  position: absolute;
  top: -30px;
  right: -30px;
  width: 110px;
  height: 110px;
  border-radius: 50%;
  filter: blur(20px);
  opacity: 0.32;
}
.pp-stat__deco--primary { background: var(--pp-color-primary); }
.pp-stat__deco--success { background: var(--pp-color-success); }
.pp-stat__deco--pink    { background: #EC4899; }

/* ---------- 列表头 ---------- */
.pp-dash__list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--pp-space-3);
  flex-wrap: wrap;
  gap: var(--pp-space-3);
}
.pp-dash__list-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  letter-spacing: -0.01em;
  color: var(--pp-color-text);
}

/* ---------- 项目网格 ---------- */
.pp-dash__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--pp-space-4);
}
@media (max-width: 1100px) { .pp-dash__grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 720px)  {
  .pp-dash__grid { grid-template-columns: 1fr; }
  .pp-dash__stats { grid-template-columns: 1fr; }
}

.pp-pcard {
  padding: var(--pp-space-5);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: var(--pp-space-3);
  min-height: 200px;
}
.pp-pcard--archived { opacity: 0.62; }
.pp-pcard__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--pp-space-3);
}
/* v0.37: 卡片右上 ⋯ 操作菜单 */
.pp-pcard__more {
  flex: none;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--pp-color-text-tertiary);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  user-select: none;
}
.pp-pcard__more:hover {
  background: var(--pp-color-bg-elevated);
  color: var(--pp-color-text);
}
.pp-pcard__check {
  margin-top: 4px;
  width: 16px;
  height: 16px;
  cursor: pointer;
}
.pp-pcard--selected {
  outline: 2px solid var(--pp-color-primary);
  outline-offset: -1px;
}
.pp-dash__list-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.pp-dash__sel-count {
  font-size: 12px;
  color: var(--pp-color-text-secondary);
}
.pp-pcard__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--pp-color-text);
  letter-spacing: -0.01em;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.pp-pcard__tag { flex: 0 0 auto; margin: 0; }

/* 4 段进度（v0.12-A 风格升级） */
.pp-pcard__progress {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}
.pp-pcard__step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  position: relative;
}
.pp-pcard__step::before {
  content: '';
  position: absolute;
  top: 4px;
  left: 50%;
  width: 100%;
  height: 2px;
  background: var(--pp-color-border);
  z-index: 0;
}
.pp-pcard__step:last-child::before { display: none; }
.pp-pcard__step--on::before { background: var(--pp-color-primary); }
.pp-pcard__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--pp-color-border);
  z-index: 1;
  transition: var(--pp-transition);
}
.pp-pcard__step--on .pp-pcard__dot {
  background: var(--pp-color-primary);
  box-shadow: 0 0 0 3px var(--pp-color-primary-soft);
}
.pp-pcard__step-label {
  font-size: 11px;
  color: var(--pp-color-text-tertiary);
  letter-spacing: 0.3px;
}
.pp-pcard__step--on .pp-pcard__step-label {
  color: var(--pp-color-primary);
  font-weight: 500;
}

.pp-pcard__desc {
  margin: 0;
  font-size: 13px;
  color: var(--pp-color-text-secondary);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}
.pp-pcard__foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: var(--pp-space-3);
  border-top: 1px solid var(--pp-color-border-soft);
}
.pp-pcard__domain {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--pp-radius-full);
  font-size: 11px;
  font-weight: 500;
  background: var(--pp-color-primary-soft);
  color: var(--pp-color-primary);
  letter-spacing: 0.3px;
}
.pp-pcard__open {
  font-size: 13px;
  font-weight: 500;
  color: var(--pp-color-primary);
  transition: var(--pp-transition);
}
.pp-pcard:hover .pp-pcard__open {
  letter-spacing: 0.5px;
}
</style>
