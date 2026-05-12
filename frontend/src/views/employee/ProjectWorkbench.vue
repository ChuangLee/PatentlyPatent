<script setup lang="ts">
/**
 * 项目工作台
 * v0.36: 左 sidebar 含文件树 | 中 chat 满宽 | 右文件预览改 Drawer 浮层（全屏/钉住/关闭）
 *   ui.previewMode: closed | drawer(default 50%) | fullscreen(100%) | pinned(回 480px 固定栏)
 */
import { onMounted, ref, computed, watch } from 'vue';
import { useRoute } from 'vue-router';
import { projectsApi } from '@/api/projects';
import { chatApi } from '@/api/chat';
import { useChatStore } from '@/stores/chat';
import { useFilesStore } from '@/stores/files';
import { useAuthStore } from '@/stores/auth';
import AgentChatStream from '@/components/chat/AgentChatStream.vue';
import FilePreviewer from '@/components/workbench/FilePreviewer.vue';
import ReadonlyBanner from '@/components/common/ReadonlyBanner.vue';
import { disclosureApi } from '@/api/disclosure';
import { filesApi } from '@/api/files';
import { takePendingUploads } from '@/stores/uploadQueue';
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
// v0.37: 重新挖掘按钮 loading
const restartMining = ref(false);

const isReadonly = computed(() => auth.role === 'admin');

/** v0.37: 是否已有挖掘历史（用于决定按钮显示"开始"还是"重新"） */
const hasMiningHistory = computed(() =>
  chat.messages.some(m => m.role === 'user' || m.role === 'agent' && (m.content || '').trim()),
);

/** v0.37: 用户手动点"开始挖掘"才启动 interview（不再 onMounted 自动跑） */
async function startMining() {
  if (!chatRef.value || chat.streaming) return;
  await chatRef.value.startFirstInterview();
}

/** v0.37: 强制重置当前项目状态 → 重新启动 interview-first（卡住时救命按钮） */
async function restartFromScratch() {
  if (!project.value || !chatRef.value || restartMining.value) return;
  restartMining.value = true;
  try {
    // 1) 取消任何在跑的 detached run
    const rid = chat.currentRunId;
    if (rid) {
      try { await chatApi.agentRuns.cancel(rid); } catch { /* ignore */ }
      chat.setCurrentRun(null);
    }
    // 2) 强制结束 streaming + 清 plan/ready 状态 + 清空消息
    chat.endAgent();
    chat.clearPlan();
    chat.setInterviewActive(false);
    chat.setReadyForDocx(false);
    chat.reset();
    // 3) 重启 interview 首轮
    await chatRef.value.startFirstInterview();
  } catch (e: any) {
    message.error('重启失败：' + (e?.message || e));
  } finally {
    restartMining.value = false;
  }
}

// v0.36: 选中文件 → 自动 open Drawer（如果当前是 closed），不打扰已 fullscreen / pinned
watch(() => files.currentFileId, (id) => {
  if (id && ui.previewMode === 'closed') ui.openPreview();
});

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

/**
 * v0.35.4: 报门时入队的二进制 attachment，进工作台后异步串行上传，
 * 进度作为 system 风格消息推到 chat（不阻塞 onMounted）。
 */
async function uploadPendingAttachments(pid: string) {
  const pending = takePendingUploads(pid);
  if (pending.length === 0) return;
  const rootUserId = `root-user-${pid}`;
  chat.appendThinking(`📤 正在上传 ${pending.length} 个附件到「我的资料」...`);
  let okCount = 0;
  for (let i = 0; i < pending.length; i++) {
    const f = pending[i];
    try {
      const node = await filesApi.upload(pid, f, rootUserId, 'user');
      if (!files.tree.some((n: FileNode) => n.id === node.id)) files.pushNode(node);
      okCount += 1;
      chat.appendThinking(`  ✓ [${i + 1}/${pending.length}] ${f.name} (${(f.size / 1024).toFixed(0)} KB)`);
    } catch (e: any) {
      chat.appendError(`  ✗ [${i + 1}/${pending.length}] ${f.name}：${e?.message || e}`);
    }
  }
  chat.appendThinking(`📤 附件上传完成（成功 ${okCount}/${pending.length}）`);
}

onMounted(async () => {
  const id = route.params.id as string;
  // 先尝试从 sessionStorage 恢复历史对话；命中则跳过后端预填
  chat.attach(id);
  const restored = chat.messages.length > 0;

  project.value = await projectsApi.get(id);

  // 装文件树（store 内部会优先用 sessionStorage 缓存，否则用传入 initialTree，否则建默认树）
  files.attach(id, project.value?.fileTree);

  // v0.35.4: 报门时入队的二进制 attachment 在此异步上传 + 进度推到 chat
  // v0.36.7: 不再 fire-and-forget；保留 promise 给下面 mineFull 等附件传完再启动
  const uploadPromise = uploadPendingAttachments(id);

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

  // v0.37: 不再自动启动挖掘。空项目时前端显示"开始挖掘"按钮让用户主动点
  // 仅在已经有 detached run 在跑时才接管恢复（上面已处理）
  // 老 mining 模式 (agent_sdk=false) 保留旧自动 autoMine 行为
  if (!resumed && project.value && project.value.status !== 'completed' && !isReadonly.value) {
    // 仅 mining 模式自动；agent_sdk 模式由用户手动点按钮
    (async () => {
      try { await uploadPromise; } catch (e: any) {
        console.warn('[upload wait]', e?.message || e);
      }
      await new Promise(r => setTimeout(r, 100));
      if (!chatRef.value || chat.streaming) return;
      const hasUserMsg = chat.messages.some(m => m.role === 'user');
      if (ui.agentMode === 'agent_sdk') {
        // agent_sdk: 等用户点"开始挖掘"按钮，这里啥都不做
        return;
      }
      if (hasUserMsg) return;   // 老 mining 模式：有用户消息说明已挖过，不重跑
      {
        const ctx = {
          title: project.value!.title,
          domain: project.value!.domain,
          customDomain: project.value!.customDomain,
          description: project.value!.description,
          intake: project.value!.intake,
        };
        chatRef.value.autoMine(ctx).catch((e: any) => {
          console.warn('[auto autoMine on enter] failed:', e?.message || e);
        });
      }
    })();
  }
});

function onRoundComplete() {
  round.value += 1;
}
</script>

<template>
  <ReadonlyBanner :show="isReadonly" />

  <!-- v0.37: 紧凑标题栏（1 行 36px 高） -->
  <div class="pp-wb-bar">
    <span class="pp-wb-title" :title="project?.title">{{ project?.title ?? '加载中...' }}</span>
    <span class="pp-wb-actions">
      <!-- v0.37: 没有任何挖掘历史时显示"开始挖掘"主按钮；已有历史时显示"重新挖掘"次按钮 -->
      <a-button v-if="!isReadonly && project && ui.agentMode === 'agent_sdk' && !hasMiningHistory"
                size="small" type="primary"
                :loading="fullMining || restartMining"
                :disabled="chat.streaming"
                @click="startMining">▶ 开始挖掘</a-button>
      <a-button v-if="!isReadonly && project && ui.agentMode === 'agent_sdk' && hasMiningHistory"
                size="small" :loading="restartMining"
                @click="restartFromScratch">🔄 重新挖掘</a-button>
      <a-button v-if="!isReadonly && project"
                size="small"
                :type="chat.readyForDocx ? 'primary' : 'default'"
                :loading="generating"
                :class="{ 'pp-btn-docx-ready': chat.readyForDocx }"
                @click="generateDisclosureDocx">🎯 生成交底书 .docx</a-button>
    </span>
  </div>

  <div class="pp-workbench-grid" :class="{ 'pp-workbench-grid-pinned': ui.previewMode === 'pinned' }">
    <!-- 中：聊天（恒满宽，pinned 时让 480px 给右栏） -->
    <div class="pp-pane pp-pane-mid">
      <AgentChatStream
        v-if="project"
        ref="chatRef"
        :project-id="project.id"
        :round="round"
        @round-complete="onRoundComplete"
      />
    </div>

    <!-- pinned 模式：右栏回固定列（兼容老布局习惯） -->
    <div v-if="ui.previewMode === 'pinned'" class="pp-pane pp-pane-right">
      <div class="pp-preview-header">
        <span class="pp-preview-title">📎 文件预览</span>
        <a-space :size="4">
          <a-tooltip title="全屏">
            <a-button size="small" type="text" @click="ui.togglePreviewFullscreen">⛶</a-button>
          </a-tooltip>
          <a-tooltip title="切换为浮层">
            <a-button size="small" type="text" @click="ui.togglePreviewPin">📌</a-button>
          </a-tooltip>
          <a-tooltip title="关闭">
            <a-button size="small" type="text" @click="ui.closePreview">×</a-button>
          </a-tooltip>
        </a-space>
      </div>
      <div class="pp-preview-body"><FilePreviewer /></div>
    </div>
  </div>

  <!-- 浮层 Drawer：drawer(50%) / fullscreen(100%)。pinned 时不显示 -->
  <a-drawer
    :open="ui.previewMode === 'drawer' || ui.previewMode === 'fullscreen'"
    :width="ui.previewMode === 'fullscreen' ? '100vw' : '50%'"
    placement="right"
    :mask="ui.previewMode === 'fullscreen'"
    :mask-closable="true"
    :closable="false"
    :body-style="{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }"
    :header-style="{ padding: '8px 16px', borderBottom: '1px solid var(--pp-color-border-soft)' }"
    @close="ui.closePreview"
  >
    <template #title>
      <div class="pp-preview-header pp-preview-header-drawer">
        <span class="pp-preview-title">📎 文件预览</span>
        <a-space :size="4">
          <a-tooltip :title="ui.previewMode === 'fullscreen' ? '退出全屏' : '全屏'">
            <a-button size="small" type="text" @click="ui.togglePreviewFullscreen">
              {{ ui.previewMode === 'fullscreen' ? '⛶ 退出全屏' : '⛶ 全屏' }}
            </a-button>
          </a-tooltip>
          <a-tooltip title="钉为固定右栏（恢复老布局）">
            <a-button size="small" type="text" @click="ui.togglePreviewPin">📌 钉住</a-button>
          </a-tooltip>
          <a-tooltip title="关闭">
            <a-button size="small" type="text" @click="ui.closePreview">× 关闭</a-button>
          </a-tooltip>
        </a-space>
      </div>
    </template>
    <FilePreviewer />
  </a-drawer>
</template>

<style scoped>
/* v0.37: 紧凑标题栏 —— 1 行 36px，靠边对齐，去掉巨大 padding */
.pp-wb-bar {
  display: flex;
  align-items: center;
  gap: var(--pp-space-3);
  padding: 6px 12px;
  margin-bottom: 8px;
  background: var(--pp-color-surface);
  border: 1px solid var(--pp-color-border-soft);
  border-radius: var(--pp-radius-md);
}
.pp-wb-title {
  flex: 1;
  font-size: 15px;
  font-weight: var(--pp-font-weight-semibold);
  color: var(--pp-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.pp-wb-actions { display: inline-flex; gap: 6px; }
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
/* v0.36: docx 按钮 ready 高亮（interview agent 发出 [READY_FOR_DOCX] 后） */
.pp-btn-docx-ready {
  animation: pp-btn-pulse 2s ease-in-out infinite;
}
@keyframes pp-btn-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(91, 108, 255, 0.4); }
  50%      { box-shadow: 0 0 0 8px rgba(91, 108, 255, 0); }
}

.pp-workbench-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--pp-space-4);
  height: calc(100vh - 120px);  /* v0.37: header 56 + content margin 16 + 紧凑标题栏 36 + grid margin 8 + 缓冲 */
  min-height: 480px;
  margin-top: var(--pp-space-4);
}
.pp-workbench-grid-pinned {
  grid-template-columns: 1fr 480px;
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
.pp-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--pp-color-border-soft);
  background: var(--pp-color-surface);
}
.pp-preview-header-drawer {
  padding: 0;
  border-bottom: none;
}
.pp-preview-title {
  font-size: 14px;
  font-weight: var(--pp-font-weight-semibold);
  color: var(--pp-color-text);
}
.pp-preview-body {
  flex: 1;
  overflow: auto;
  min-height: 0;
}

@media (max-width: 1280px) {
  .pp-workbench-grid-pinned {
    grid-template-columns: 1fr 420px;
  }
}
@media (max-width: 1024px) {
  .pp-workbench-grid-pinned {
    grid-template-columns: 1fr;
  }
  .pp-pane-right { display: none; }
}
</style>
