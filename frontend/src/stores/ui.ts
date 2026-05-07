import { defineStore } from 'pinia';
import { ref, watch } from 'vue';

const KEY = 'pp.ui';

interface UIState {
  theme: 'light' | 'dark';
  sidebarCollapsed: boolean;
  workbenchSplitView?: boolean;
}

function load(): UIState {
  if (typeof localStorage === 'undefined') {
    return { theme: 'light', sidebarCollapsed: false, workbenchSplitView: false };
  }
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) ?? '') as UIState;
    return {
      theme: parsed.theme ?? 'light',
      sidebarCollapsed: parsed.sidebarCollapsed ?? false,
      workbenchSplitView: parsed.workbenchSplitView ?? false,
    };
  }
  catch { return { theme: 'light', sidebarCollapsed: false, workbenchSplitView: false }; }
}

export const useUIStore = defineStore('ui', () => {
  const initial = load();
  const theme = ref<'light' | 'dark'>(initial.theme);
  const sidebarCollapsed = ref(initial.sidebarCollapsed);
  const workbenchSplitView = ref<boolean>(initial.workbenchSplitView ?? false);

  function toggleTheme() { theme.value = theme.value === 'light' ? 'dark' : 'light'; }
  function toggleSidebar() { sidebarCollapsed.value = !sidebarCollapsed.value; }
  function toggleWorkbenchSplitView() { workbenchSplitView.value = !workbenchSplitView.value; }

  watch([theme, sidebarCollapsed, workbenchSplitView], () => {
    localStorage.setItem(KEY, JSON.stringify({
      theme: theme.value,
      sidebarCollapsed: sidebarCollapsed.value,
      workbenchSplitView: workbenchSplitView.value,
    }));
  });

  return {
    theme, sidebarCollapsed, workbenchSplitView,
    toggleTheme, toggleSidebar, toggleWorkbenchSplitView,
  };
});
