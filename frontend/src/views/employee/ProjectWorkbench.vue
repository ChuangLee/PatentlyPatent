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
import ReadonlyBanner from '@/components/common/ReadonlyBanner.vue';
import type { Project, ProjectStatus } from '@/types';

const route = useRoute();
const chat = useChatStore();
const files = useFilesStore();
const auth = useAuthStore();

const project = ref<Project | null>(null);
const round = ref(1);

const isReadonly = computed(() => auth.role === 'admin');

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

onMounted(async () => {
  chat.reset();
  const id = route.params.id as string;
  project.value = await projectsApi.get(id);

  // 装文件树（store 内部会优先用 sessionStorage 缓存，否则用传入 initialTree，否则建默认树）
  files.attach(id, project.value?.fileTree);

  // 预填已有 conversation
  if (project.value?.miningSummary?.conversation.length) {
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
    round.value =
      project.value.miningSummary.conversation.filter(m => m.role === 'agent').length + 1;
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
    <template #footer>
      <a-steps
        v-if="project"
        :current="currentStep"
        size="small"
        style="margin-top:8px"
      >
        <a-step title="报门" />
        <a-step title="挖掘" />
        <a-step title="检索" />
        <a-step title="撰写" />
        <a-step title="完成" />
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

    <!-- 右：文件预览 -->
    <div class="pp-pane pp-pane-right">
      <FilePreviewer />
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
