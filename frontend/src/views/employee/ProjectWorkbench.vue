<script setup lang="ts">
/**
 * 项目工作台 — 三栏布局
 * 左：文件树 | 中：通用 AI 聊天 | 右：文件预览
 */
import { onMounted, ref, computed } from 'vue';
import { useRoute } from 'vue-router';
import { projectsApi } from '@/api/projects';
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

const isReadonly = computed(() => auth.role === 'admin');

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
});

function onRoundComplete() {
  round.value += 1;
}
</script>

<template>
  <ReadonlyBanner :show="isReadonly" />

  <a-page-header
    :title="project?.title ?? '加载中...'"
    sub-title="工作台 · 文件 + AI 对话 + 预览"
  >
    <template #extra>
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
        style="margin-top:8px"
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
        style="margin-top:12px"
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

  <div class="pp-workbench-grid">
    <!-- 左：聊天 -->
    <div class="pp-pane pp-pane-mid">
      <AgentChatStream
        v-if="project"
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
.pp-workbench-grid {
  display: grid;
  grid-template-columns: 1fr 480px;
  gap: 12px;
  height: calc(100vh - 260px);
  min-height: 480px;
  margin-top: 12px;
}
.pp-pane {
  border: 1px solid #eee;
  border-radius: 8px;
  background: #fff;
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
  border-bottom: 1px solid #eee;
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
  box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.25);
  animation: pp-split-glow 1.6s ease-in-out infinite;
}
@keyframes pp-split-glow {
  0%, 100% { box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.25); }
  50% { box-shadow: 0 0 0 4px rgba(22, 119, 255, 0.45); }
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
