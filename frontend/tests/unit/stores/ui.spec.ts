import { describe, it, expect, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useUIStore } from '@/stores/ui';
import { nextTick } from 'vue';

describe('useUIStore', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it('默认 light + 不折叠', () => {
    const s = useUIStore();
    expect(s.theme).toBe('light');
    expect(s.sidebarCollapsed).toBe(false);
  });

  it('toggleTheme 切换并持久化', async () => {
    const s = useUIStore();
    s.toggleTheme();
    await nextTick();
    expect(s.theme).toBe('dark');
    const persisted = JSON.parse(localStorage.getItem('pp.ui')!);
    expect(persisted.theme).toBe('dark');
  });

  it('toggleSidebar 切换并持久化', async () => {
    const s = useUIStore();
    s.toggleSidebar();
    await nextTick();
    expect(s.sidebarCollapsed).toBe(true);
  });
});
