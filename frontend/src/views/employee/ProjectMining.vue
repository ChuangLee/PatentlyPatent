<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { useChatStore } from '@/stores/chat';
import { useAuthStore } from '@/stores/auth';
import AgentChatStream from '@/components/chat/AgentChatStream.vue';
import MiningSummaryPanel from '@/components/chat/MiningSummaryPanel.vue';
import ReadonlyBanner from '@/components/common/ReadonlyBanner.vue';
import type { Project } from '@/types';
import { message } from 'ant-design-vue';

const route = useRoute();
const router = useRouter();
const chat = useChatStore();
const auth = useAuthStore();

const project = ref<Project | null>(null);
const round = ref(1);

const isReadonly = computed(() => auth.role === 'admin');

onMounted(async () => {
  const id = route.params.id as string;
  // 先尝试从 sessionStorage 恢复；命中跳过后端预填
  chat.attach(id);
  const restored = chat.messages.length > 0;

  project.value = await projectsApi.get(id);

  if (!restored && project.value?.miningSummary?.conversation.length) {
    for (const m of project.value.miningSummary.conversation) {
      if (m.role === 'user') chat.appendUser(m.content);
      else {
        chat.startAgent();
        chat.appendDelta(m.content);
        chat.endAgent();
      }
    }
    chat.applyFields(
      [...project.value.miningSummary.field.map(x => `领域:${x}`),
       ...project.value.miningSummary.problem.map(x => `问题:${x}`),
       ...project.value.miningSummary.means.map(x => `手段:${x}`),
       ...project.value.miningSummary.effect.map(x => `效果:${x}`),
       ...project.value.miningSummary.differentiator.map(x => `区别:${x}`)],
    );
  }

  if (chat.messages.length) {
    round.value = chat.messages.filter(m => m.role === 'agent').length + 1;
  }
});

function onRoundComplete() {
  round.value += 1;
}

function done() {
  message.success('要素已捕获完整，进入检索阶段');
  router.push(`/employee/projects/${route.params.id}/search`);
}
</script>

<template>
  <ReadonlyBanner :show="isReadonly" />
  <a-page-header :title="project?.title ?? '加载中...'"
                 sub-title="AI 引导对话 · 把模糊的发现拆成结构化创新点" />

  <div style="display:flex;height:calc(100vh - 240px);gap:16px">
    <div style="flex:1.5;border:1px solid #eee;border-radius:8px;display:flex;flex-direction:column">
      <AgentChatStream v-if="project" :project-id="project.id" :round="round"
                       @round-complete="onRoundComplete" />
    </div>

    <div style="flex:1;border:1px solid #eee;border-radius:8px;background:#fff;overflow-y:auto">
      <MiningSummaryPanel />
      <div style="padding:0 16px 16px">
        <a-button v-if="!isReadonly" type="primary" block size="large" @click="done">
          差不多了 →
        </a-button>
      </div>
    </div>
  </div>
</template>
