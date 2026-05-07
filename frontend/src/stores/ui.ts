import { defineStore } from 'pinia';
import { ref, watch } from 'vue';

const KEY = 'pp.ui';

interface UIState {
  theme: 'light' | 'dark';
  sidebarCollapsed: boolean;
}

function load(): UIState {
  if (typeof localStorage === 'undefined') return { theme: 'light', sidebarCollapsed: false };
  try { return JSON.parse(localStorage.getItem(KEY) ?? '') as UIState; }
  catch { return { theme: 'light', sidebarCollapsed: false }; }
}

export const useUIStore = defineStore('ui', () => {
  const initial = load();
  const theme = ref<'light' | 'dark'>(initial.theme);
  const sidebarCollapsed = ref(initial.sidebarCollapsed);

  function toggleTheme() { theme.value = theme.value === 'light' ? 'dark' : 'light'; }
  function toggleSidebar() { sidebarCollapsed.value = !sidebarCollapsed.value; }

  watch([theme, sidebarCollapsed], () => {
    localStorage.setItem(KEY, JSON.stringify({
      theme: theme.value,
      sidebarCollapsed: sidebarCollapsed.value,
    }));
  });

  return { theme, sidebarCollapsed, toggleTheme, toggleSidebar };
});
