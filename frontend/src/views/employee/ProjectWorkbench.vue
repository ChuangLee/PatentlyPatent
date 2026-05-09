<script setup lang="ts">
/**
 * 项目工作台 — 三栏布局
 * 左：文件树 | 中：通用 AI 聊天 | 右：文件预览
 */
import { onMounted, ref, computed } from 'vue';
import { useRoute } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { chatApi } from '@/api/chat';
import { useChatStore } from '@/stores/chat';
import { useFilesStore } from '@/stores/files';
import { useAuthStore } from '@/stores/auth';
import AgentChatStream from '@/components/chat/AgentChatStream.vue';
import FilePreviewer from '@/components/workbench/FilePreviewer.vue';
import MiniChatView from '@/components/chat/MiniChatView.vue';
import ReadonlyBanner from '@/components/common/ReadonlyBanner.vue';
import { disclosureApi } from '@/api/disclosure';
import message from 'ant-design-vue/es/message';
import { useUIStore } from '@/stores/ui';
import type { Project, ProjectStatus, FileNode } from '@/types';

const route = useRoute();
const chat = useChatStore();
const files = useFilesStore();
const auth = useAuthStore();
const ui = useUIStore();

const project = ref<Project | null>(null);
const round = ref(1);
const chatRef = ref<InstanceType<typeof AgentChatStream> | null>(null);
const generating = ref(false);
// v0.21 任务 1: 一键全程挖掘 loading
const fullMining = ref(false);

const isReadonly = computed(() => auth.role === 'admin');

/** v0.21 任务 1: 触发 mine_full 一键端到端 */
async function runFullMining() {
  if (!project.value || fullMining.value || chat.streaming) return;
  if (!chatRef.value) {
    message.error('聊天组件未就绪');
    return;
  }
  fullMining.value = true;
  try {
    const idea = [
      project.value.title,
      project.value.description,
      project.value.intake?.notes,
    ].filter(Boolean).join('\n');
    await chatRef.value.mineFull(idea || '（无描述）');
    // disclosure 路由 redirect 回 workbench，所以不真正跳转 — 提示成功即可
    message.success('一键全程挖掘完成 ✓');
  } catch (e) {
    // mineFull 内部已经 message.error 过了，这里不重复
    console.error('[runFullMining]', e);
  } finally {
    fullMining.value = false;
    chat.endAgent();
  }
}

async function generateDisclosureDocx() {
  if (!project.value) return;
  generating.value = true;
  try {
    const resp = await disclosureApi.generateDocx(project.value.id);
    const node: FileNode = resp.file;
    const exists = files.tree.find(n => n.id === node.id);
    if (!exists) files.pushNode(node);
    files.selectFile(node.id);
    message.success('交底书已生成 → AI 输出/' + node.name);
    if (project.value && resp.projectStatus) project.value.status = resp.projectStatus as ProjectStatus;
  } catch (e) {
    message.error('生成失败：' + (e as Error).message);
  } finally {
    generating.value = false;
  }
}

/** status → a-steps current（0-based） */
const STATUS_STEP: Record<ProjectStatus, number> = {
  drafting: 1,
  researching: 1,
  reporting: 2,
  completed: 4,
};

const currentStep = computed(() =>
  project.value ? STATUS_STEP[project.value.status] : 0,
);

// v0.20 Wave1 任务 1: 5 章节进度条配置
const SECTION_STEPS = [
  { key: 'prior_art', title: '现有技术' },
  { key: 'summary', title: '发明内容' },
  { key: 'embodiments', title: '实施例' },
  { key: 'claims', title: '权利要求' },
  { key: 'drawings_description', title: '附图' },
] as const;

/** a-step status: 'wait' | 'process' | 'finish' | 'error' */
function stepStatus(key: string): 'wait' | 'process' | 'finish' | 'error' {
  const s = chat.sectionProgress[key];
  if (s === 'running') return 'process';
  if (s === 'done') return 'finish';
  if (s === 'error') return 'error';
  return 'wait';
}

/** 用于 a-steps current（取第一条 running 章节，否则取已完成数） */
const sectionCurrentIdx = computed(() => {
  const runningIdx = SECTION_STEPS.findIndex(s => chat.sectionProgress[s.key] === 'running');
  if (runningIdx >= 0) return runningIdx;
  const done = SECTION_STEPS.filter(s => chat.sectionProgress[s.key] === 'done').length;
  return done;
});

onMounted(async () => {
  const id = route.params.id as string;
  // 先尝试从 sessionStorage 恢复历史对话；命中则跳过后端预填
  chat.attach(id);
  const restored = chat.messages.length > 0;

  project.value = await projectsApi.get(id);

  // 装文件树（store 内部会优先用 sessionStorage 缓存，否则用传入 initialTree，否则建默认树）
  files.attach(id, project.value?.fileTree);

  if (!restored && project.value?.miningSummary?.conversation.length) {
    // 首次进入：用后端 miningSummary 预填，attach 内部会 persist
    for (const m of project.value.miningSummary.conversation) {
      if (m.role === 'user') {
        chat.appendUser(m.content);
      } else {
        chat.startAgent();
        chat.appendDelta(m.content);
        chat.endAgent();
      }
    }
    chat.applyFields(
      [
        ...project.value.miningSummary.field.map(x => `领域:${x}`),
        ...project.value.miningSummary.problem.map(x => `问题:${x}`),
        ...project.value.miningSummary.means.map(x => `手段:${x}`),
        ...project.value.miningSummary.effect.map(x => `效果:${x}`),
        ...project.value.miningSummary.differentiator.map(x => `区别:${x}`),
      ],
    );
  }

  // 推断 round：以已完成 agent 消息数 + 1 为下一轮
  if (chat.messages.length) {
    round.value = chat.messages.filter(m => m.role === 'agent').length + 1;
  }

  // v0.34: 优先检查后端是否有 in-flight run（detached 跑着的）— 接管恢复
  let resumed = false;
  if (project.value && !isReadonly.value) {
    try {
      const active = await chatApi.agentRuns.active(project.value.id);
      if (active && active.status === 'running') {
        // 用 sessionStorage 缓存的 lastEventSeq 续传
        const since = chat.currentRunId === active.id ? (chat.lastEventSeq || 0) : 0;
        // 让 chat 组件挂载后调用 resumeRun
        setTimeout(() => {
          if (chatRef.value) chatRef.value.resumeRun(active.id, since);
        }, 100);
        resumed = true;
      } else if (chat.currentRunId) {
        // 本地 run id 但服务端已终态：拉历史 events 一次性回放
        const rid = chat.currentRunId;
        try {
          const info = await chatApi.agentRuns.get(rid);
          if (info.status !== 'running') {
            setTimeout(() => {
              if (chatRef.value) chatRef.value.resumeRun(rid, 0);
            }, 100);
            resumed = true;
          }
        } catch { /* run 不存在了：忽略 */ }
      }
    } catch (e) {
      console.warn('[active run lookup]', (e as Error).message);
    }
  }

  // v0.33 + v0.34.3: 没接管运行中 run + 没历史回放 → 自动启动挖掘
  // 关键：不限制 status='drafting'（auto-mining 后台会改成 researching）
  // 关键：用 hasMeaningfulContent 而不是 length===0（attach 已清掉空 agent 残留）
  const hasMeaningfulContent = chat.messages.some(
    m => m.role === 'user' || (m.content && m.content.trim().length > 0),
  );
  const isFreshDraft = !resumed
    && !hasMeaningfulContent
    && project.value
    && project.value.status !== 'completed'
    && !isReadonly.value;
  if (isFreshDraft) {
    // 给一点时间让 chat 组件挂载完成
    setTimeout(() => {
      if (!chatRef.value || chat.streaming) return;
      const idea = [
        project.value!.title,
        project.value!.description,
        project.value!.intake?.notes,
      ].filter(Boolean).join('\n');
      // agent_sdk 模式优先 mineFull，老 mining 模式走 autoMine
      const ctx = {
        title: project.value!.title,
        domain: project.value!.domain,
        customDomain: project.value!.customDomain,
        description: project.value!.description,
        intake: project.value!.intake,
      };
      if (ui.agentMode === 'agent_sdk') {
        chatRef.value.mineFull(idea || '（无描述）').catch((e: any) => {
          console.warn('[auto mineFull on enter] failed:', e?.message || e);
        });
      } else {
        chatRef.value.autoMine(ctx).catch((e: any) => {
          console.warn('[auto autoMine on enter] failed:', e?.message || e);
        });
      }
    }, 300);
  }
});

function onRoundComplete() {
  round.value += 1;
}
</script>

<template>
  <ReadonlyBanner :show="isReadonly" />

  <div class="pp-workbench-header pp-card">
    <a-page-header
      :title="project?.title ?? '加载中...'"
      sub-title="工作台 · 文件 + AI 对话 + 预览"
      class="pp-workbench-page-header"
    >
      <template #extra>
        <!-- v0.21 任务 1: 一键全程挖掘（仅 agent_sdk 模式可见） -->
        <a-button
          v-if="!isReadonly && project && ui.agentMode === 'agent_sdk'"
          type="primary"
          :loading="fullMining"
          :disabled="chat.streaming && !fullMining"
          class="pp-btn-onekey"
          @click="runFullMining"
        >
          ⚡ 一键全程挖掘
        </a-button>
        <a-button
          v-if="project"
          :type="ui.workbenchSplitView ? 'primary' : 'default'"
          :ghost="ui.workbenchSplitView"
          :class="{ 'pp-split-btn-active': chat.streaming }"
          @click="ui.toggleWorkbenchSplitView"
        >
          📑 {{ ui.workbenchSplitView ? '关闭 split view' : '切 split view' }}
        </a-button>
        <a-button
          v-if="!isReadonly && project"
          type="primary"
          :loading="generating"
          @click="generateDisclosureDocx"
        >
          🎯 生成交底书 .docx
        </a-button>
      </template>
      <template #footer>
        <a-steps
          v-if="project"
          :current="currentStep"
          size="small"
          class="pp-workbench-steps"
        >
          <a-step title="报门（提交创意）" />
          <a-step title="挖掘" />
          <a-step title="检索" />
          <a-step title="撰写" />
          <a-step title="完成" />
        </a-steps>
        <!-- v0.20 Wave1 任务 1: 5 章节并行进度（仅 agent_sdk 模式显示） -->
        <a-steps
          v-if="ui.agentMode === 'agent_sdk'"
          :current="sectionCurrentIdx"
          size="small"
          class="pp-workbench-steps pp-workbench-steps-sections"
        >
          <a-step
            v-for="s in SECTION_STEPS"
            :key="s.key"
            :title="s.title"
            :status="stepStatus(s.key)"
          />
        </a-steps>
      </template>
    </a-page-header>
  </div>

  <div class="pp-workbench-grid">
    <!-- 左：聊天 -->
    <div class="pp-pane pp-pane-mid">
      <AgentChatStream
        v-if="project"
        ref="chatRef"
        :project-id="project.id"
        :round="round"
        @round-complete="onRoundComplete"
      />
    </div>

    <!-- 右：文件预览（split view 时上半 mini chat / 下半预览）-->
    <div
      class="pp-pane pp-pane-right"
      :class="{ 'pp-pane-right-split': ui.workbenchSplitView }"
    >
      <template v-if="ui.workbenchSplitView">
        <div class="pp-pane-split-top">
          <MiniChatView :tail="8" />
        </div>
        <div class="pp-pane-split-bottom">
          <FilePreviewer />
        </div>
      </template>
      <FilePreviewer v-else />
    </div>
  </div>
</template>

<style scoped>
.pp-workbench-header {
  margin-bottom: var(--pp-space-4);
}
.pp-card {
  background: var(--pp-color-surface);
  border-radius: var(--pp-radius-lg);
  box-shadow: var(--pp-shadow-sm);
  border: 1px solid var(--pp-color-border-soft);
  padding: var(--pp-space-5);
}
.pp-workbench-page-header {
  padding: 0 !important;
  font-family: var(--pp-font-sans);
}
.pp-workbench-steps {
  margin-top: var(--pp-space-3);
  min-height: 48px;
}
.pp-workbench-steps-sections {
  margin-top: var(--pp-space-3);
}

/* ---------- 5 步 timeline 紧凑布局（48px 高） ---------- */
.pp-workbench-steps :deep(.ant-steps-item-icon) {
  width: 24px;
  height: 24px;
  line-height: 22px;
  margin-inline-end: 8px;
  font-size: 12px;
  border-width: 1.5px;
  transition: var(--pp-transition);
}
.pp-workbench-steps :deep(.ant-steps-item-title) {
  font-size: var(--pp-font-size-sm);
  line-height: 24px;
  padding-inline-end: 12px;
}
.pp-workbench-steps :deep(.ant-steps-item-tail) {
  top: 12px;
  padding: 0 10px;
}
.pp-workbench-steps :deep(.ant-steps-item-tail::after) {
  height: 2px;
  border-radius: 1px;
  background: var(--pp-color-border);
}

/* ---------- finish (done): primary 实心 + ✓ ---------- */
.pp-workbench-steps :deep(.ant-steps-item-finish .ant-steps-item-icon) {
  background: var(--pp-color-primary);
  border-color: var(--pp-color-primary);
}
.pp-workbench-steps :deep(.ant-steps-item-finish .ant-steps-item-icon > .ant-steps-icon) {
  color: var(--pp-color-text-inverse);
}
.pp-workbench-steps :deep(.ant-steps-item-finish > .ant-steps-item-container > .ant-steps-item-content > .ant-steps-item-title) {
  color: var(--pp-color-text);
  font-weight: var(--pp-font-weight-medium);
}
/* finish 段连接线：primary 渐变实色 */
.pp-workbench-steps :deep(.ant-steps-item-finish > .ant-steps-item-container > .ant-steps-item-tail::after) {
  background: linear-gradient(90deg, var(--pp-color-primary), var(--pp-color-primary-hover));
}

/* ---------- process (running): primary 实心 + 呼吸 halo ---------- */
.pp-workbench-steps :deep(.ant-steps-item-process .ant-steps-item-icon) {
  background: var(--pp-color-primary);
  border-color: var(--pp-color-primary);
  animation: pp-step-halo 1.6s ease-in-out infinite;
}
.pp-workbench-steps :deep(.ant-steps-item-process .ant-steps-item-icon > .ant-steps-icon) {
  color: var(--pp-color-text-inverse);
}
.pp-workbench-steps :deep(.ant-steps-item-process > .ant-steps-item-container > .ant-steps-item-content > .ant-steps-item-title) {
  color: var(--pp-color-primary);
  font-weight: var(--pp-font-weight-semibold);
}
@keyframes pp-step-halo {
  0%, 100% { box-shadow: 0 0 0 3px rgba(91, 108, 255, 0.18); }
  50%      { box-shadow: 0 0 0 6px rgba(91, 108, 255, 0.32); }
}

/* ---------- wait (pending): 空心 + border-soft ---------- */
.pp-workbench-steps :deep(.ant-steps-item-wait .ant-steps-item-icon) {
  background: var(--pp-color-surface);
  border-color: var(--pp-color-border-strong);
}
.pp-workbench-steps :deep(.ant-steps-item-wait .ant-steps-item-icon > .ant-steps-icon) {
  color: var(--pp-color-text-tertiary);
}
.pp-workbench-steps :deep(.ant-steps-item-wait > .ant-steps-item-container > .ant-steps-item-content > .ant-steps-item-title) {
  color: var(--pp-color-text-tertiary);
}

/* error */
.pp-workbench-steps :deep(.ant-steps-item-error .ant-steps-item-icon) {
  background: var(--pp-color-danger-soft);
  border-color: var(--pp-color-danger);
}
.pp-workbench-steps :deep(.ant-steps-item-error .ant-steps-item-icon > .ant-steps-icon) {
  color: var(--pp-color-danger);
}

/* 一键全程按钮 */
.pp-btn-onekey {
  border-radius: var(--pp-radius-md) !important;
  background: var(--pp-color-primary) !important;
  border-color: var(--pp-color-primary) !important;
  font-weight: var(--pp-font-weight-medium);
  transition: var(--pp-transition);
}
.pp-btn-onekey:hover {
  background: var(--pp-color-primary-hover) !important;
  border-color: var(--pp-color-primary-hover) !important;
  box-shadow: var(--pp-shadow-md);
  transform: translateY(-1px);
}

.pp-workbench-grid {
  display: grid;
  grid-template-columns: 1fr 480px;
  gap: var(--pp-space-4);
  height: calc(100vh - 280px);
  min-height: 480px;
  margin-top: var(--pp-space-4);
}
.pp-pane {
  border: 1px solid var(--pp-color-border-soft);
  border-radius: var(--pp-radius-lg);
  background: var(--pp-color-surface);
  box-shadow: var(--pp-shadow-sm);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.pp-pane-right { min-width: 380px; }
.pp-pane-right-split {
  display: grid;
  grid-template-rows: 1fr 1fr;
  gap: 0;
}
.pp-pane-split-top {
  border-bottom: 1px solid var(--pp-color-border-soft);
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.pp-pane-split-bottom {
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.pp-split-btn-active {
  box-shadow: var(--pp-shadow-focus);
  animation: pp-split-glow 1.6s ease-in-out infinite;
}
@keyframes pp-split-glow {
  0%, 100% { box-shadow: 0 0 0 2px rgba(91, 108, 255, 0.25); }
  50%      { box-shadow: 0 0 0 4px rgba(91, 108, 255, 0.45); }
}

@media (max-width: 1280px) {
  .pp-workbench-grid {
    grid-template-columns: 1fr 420px;
  }
}
@media (max-width: 1024px) {
  .pp-workbench-grid {
    grid-template-columns: 1fr;
  }
  .pp-pane-right { display: none; }
}
</style>
