import { defineStore } from 'pinia';
import { ref, watch } from 'vue';

const KEY = 'pp.ui';

export type AgentMode = 'mining' | 'agent_sdk';

export type PreviewMode = 'closed' | 'drawer' | 'fullscreen' | 'pinned';

interface UIState {
  theme: 'light' | 'dark';
  sidebarCollapsed: boolean;
  workbenchSplitView?: boolean;
  agentMode?: AgentMode;
  previewMode?: PreviewMode;
}

function load(): UIState {
  // v0.37: agent_sdk 是唯一生产路径，强制覆盖任何缓存里的 'mining'
  const fallback: UIState = {
    theme: 'light', sidebarCollapsed: false, workbenchSplitView: false,
    agentMode: 'agent_sdk', previewMode: 'closed',
  };
  if (typeof localStorage === 'undefined') return fallback;
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) ?? '') as UIState;
    return {
      theme: parsed.theme ?? 'light',
      sidebarCollapsed: parsed.sidebarCollapsed ?? false,
      workbenchSplitView: parsed.workbenchSplitView ?? false,
      agentMode: 'agent_sdk',   // 强制：忽略缓存里的旧值（mining 已弃用）
      previewMode: parsed.previewMode ?? 'closed',
    };
  }
  catch { return fallback; }
}

export const useUIStore = defineStore('ui', () => {
  const initial = load();
  const theme = ref<'light' | 'dark'>(initial.theme);
  const sidebarCollapsed = ref(initial.sidebarCollapsed);
  const workbenchSplitView = ref<boolean>(initial.workbenchSplitView ?? false);
  const agentMode = ref<AgentMode>(initial.agentMode ?? 'agent_sdk');
  const previewMode = ref<PreviewMode>(initial.previewMode ?? 'closed');

  function toggleTheme() { theme.value = theme.value === 'light' ? 'dark' : 'light'; }
  function toggleSidebar() { sidebarCollapsed.value = !sidebarCollapsed.value; }
  function toggleWorkbenchSplitView() { workbenchSplitView.value = !workbenchSplitView.value; }
  function setAgentMode(m: AgentMode) { agentMode.value = m; }
  function setPreviewMode(m: PreviewMode) { previewMode.value = m; }
  function openPreview() {
    if (previewMode.value === 'closed') previewMode.value = 'drawer';
  }
  function closePreview() { previewMode.value = 'closed'; }
  function togglePreviewFullscreen() {
    previewMode.value = previewMode.value === 'fullscreen' ? 'drawer' : 'fullscreen';
  }
  function togglePreviewPin() {
    previewMode.value = previewMode.value === 'pinned' ? 'drawer' : 'pinned';
  }

  watch([theme, sidebarCollapsed, workbenchSplitView, agentMode, previewMode], () => {
    localStorage.setItem(KEY, JSON.stringify({
      theme: theme.value,
      sidebarCollapsed: sidebarCollapsed.value,
      workbenchSplitView: workbenchSplitView.value,
      agentMode: agentMode.value,
      previewMode: previewMode.value,
    }));
  });

  return {
    theme, sidebarCollapsed, workbenchSplitView, agentMode, previewMode,
    toggleTheme, toggleSidebar, toggleWorkbenchSplitView, setAgentMode,
    setPreviewMode, openPreview, closePreview,
    togglePreviewFullscreen, togglePreviewPin,
  };
});
