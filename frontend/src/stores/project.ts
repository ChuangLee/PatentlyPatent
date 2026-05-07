import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Project, ProjectStatus } from '@/types';

const KEY = 'pp.projects';

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>(loadProjects());
  const currentId = ref<string | null>(null);

  function loadProjects(): Project[] {
    if (typeof sessionStorage === 'undefined') return [];
    const raw = sessionStorage.getItem(KEY);
    try { return raw ? JSON.parse(raw) as Project[] : []; } catch { return []; }
  }

  function persist() {
    sessionStorage.setItem(KEY, JSON.stringify(projects.value));
  }

  function setAll(list: Project[]) {
    projects.value = list;
    persist();
  }

  function upsert(p: Project) {
    const idx = projects.value.findIndex(x => x.id === p.id);
    if (idx >= 0) projects.value[idx] = p;
    else projects.value.push(p);
    persist();
  }

  function setStatus(id: string, status: ProjectStatus) {
    const p = projects.value.find(x => x.id === id);
    if (!p) return;
    p.status = status;
    p.updatedAt = new Date().toISOString();
    persist();
  }

  function setCurrent(id: string | null) { currentId.value = id; }
  const current = computed(() =>
    projects.value.find(p => p.id === currentId.value) ?? null
  );

  function getById(id: string): Project | null {
    return projects.value.find(p => p.id === id) ?? null;
  }

  return { projects, currentId, current, setAll, upsert, setStatus, setCurrent, getById };
});
