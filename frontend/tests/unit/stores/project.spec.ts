import { describe, it, expect, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useProjectStore } from '@/stores/project';
import type { Project } from '@/types';

const sample: Project = {
  id: 'p1', title: 't', domain: 'ai', description: 'd',
  status: 'drafting', ownerId: 'u1',
  createdAt: '2026-05-07T00:00:00Z', updatedAt: '2026-05-07T00:00:00Z',
};

describe('useProjectStore', () => {
  beforeEach(() => {
    sessionStorage.clear();
    setActivePinia(createPinia());
  });

  it('初始为空', () => {
    const s = useProjectStore();
    expect(s.projects).toEqual([]);
    expect(s.current).toBeNull();
  });

  it('upsert 新增并持久化', () => {
    const s = useProjectStore();
    s.upsert(sample);
    expect(s.projects).toHaveLength(1);
    expect(JSON.parse(sessionStorage.getItem('pp.projects')!)).toHaveLength(1);
  });

  it('upsert 同 id 覆盖', () => {
    const s = useProjectStore();
    s.upsert(sample);
    s.upsert({ ...sample, title: 't2' });
    expect(s.projects).toHaveLength(1);
    expect(s.projects[0].title).toBe('t2');
  });

  it('setStatus 更新状态与时间', () => {
    const s = useProjectStore();
    s.upsert(sample);
    const before = s.projects[0].updatedAt;
    s.setStatus('p1', 'submitted');
    expect(s.projects[0].status).toBe('submitted');
    expect(s.projects[0].updatedAt).not.toBe(before);
  });

  it('setCurrent + current computed 联动', () => {
    const s = useProjectStore();
    s.upsert(sample);
    s.setCurrent('p1');
    expect(s.current?.id).toBe('p1');
  });

  it('getById 找到/找不到', () => {
    const s = useProjectStore();
    s.upsert(sample);
    expect(s.getById('p1')?.id).toBe('p1');
    expect(s.getById('xxx')).toBeNull();
  });
});
