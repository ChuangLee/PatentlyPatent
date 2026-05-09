import { describe, it, expect, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { createRouter, createMemoryHistory } from 'vue-router';
import UsageTutorial from '@/components/tutorial/UsageTutorial.vue';

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div/>' } }],
  });
}

describe('UsageTutorial 界面', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('渲染 6 个章节 step', () => {
    const w = mount(UsageTutorial, { global: { plugins: [makeRouter(), createPinia()] } });
    const html = w.html();
    expect(html).toContain('报门');
    expect(html).toContain('5 步');
    expect(html).toContain('Agent');
    expect(html).toContain('文件树');
    expect(html).toContain('答问');
    expect(html).toContain('导出');
  });

  it('emits start / skip 事件', async () => {
    const w = mount(UsageTutorial, { global: { plugins: [makeRouter(), createPinia()] } });
    const buttons = w.findAll('button');
    const startBtn = buttons.find(b => b.text().includes('立即开始'));
    const skipBtn = buttons.find(b => b.text().includes('跳过'));
    expect(startBtn).toBeTruthy();
    expect(skipBtn).toBeTruthy();
    await startBtn!.trigger('click');
    await skipBtn!.trigger('click');
    expect(w.emitted('start')).toBeTruthy();
    expect(w.emitted('skip')).toBeTruthy();
  });
});
