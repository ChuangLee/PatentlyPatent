import { defineStore } from 'pinia';
import { ref, watch } from 'vue';

const KEY = 'pp.ui';

export type AgentMode = 'mining' | 'agent_sdk';

interface UIState {
  theme: 'light' | 'dark';
  sidebarCollapsed: boolean;
  workbenchSplitView?: boolean;
  agentMode?: AgentMode;
}

function load(): UIState {
  // v0.35.5: 默认 agent_sdk 走真 LLM（agent SDK + claude CLI OAuth）
  // mining 老路径需要 ANTHROPIC_API_KEY，当前 prod 未配置 → 默认走 mock 字符串
  const fallback: UIState = { theme: 'light', sidebarCollapsed: false, workbenchSplitView: false, agentMode: 'agent_sdk' };
  if (typeof localStorage === 'undefined') return fallback;
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) ?? '') as UIState;
    return {
      theme: parsed.theme ?? 'light',
      sidebarCollapsed: parsed.sidebarCollapsed ?? false,
      workbenchSplitView: parsed.workbenchSplitView ?? false,
      agentMode: parsed.agentMode ?? 'agent_sdk',
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

  function toggleTheme() { theme.value = theme.value === 'light' ? 'dark' : 'light'; }
  function toggleSidebar() { sidebarCollapsed.value = !sidebarCollapsed.value; }
  function toggleWorkbenchSplitView() { workbenchSplitView.value = !workbenchSplitView.value; }
  function setAgentMode(m: AgentMode) { agentMode.value = m; }

  watch([theme, sidebarCollapsed, workbenchSplitView, agentMode], () => {
    localStorage.setItem(KEY, JSON.stringify({
      theme: theme.value,
      sidebarCollapsed: sidebarCollapsed.value,
      workbenchSplitView: workbenchSplitView.value,
      agentMode: agentMode.value,
    }));
  });

  return {
    theme, sidebarCollapsed, workbenchSplitView, agentMode,
    toggleTheme, toggleSidebar, toggleWorkbenchSplitView, setAgentMode,
  };
});
