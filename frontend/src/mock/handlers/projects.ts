import { http, HttpResponse } from 'msw';
import type { Project, Domain, Attachment } from '@/types';
import { ALL_CASES } from '../fixtures/all_cases';

// 内存中可变项目仓（基于 ALL_CASES 拷贝，演示用）
const store: Project[] = JSON.parse(JSON.stringify(ALL_CASES));

export const projectsHandlers = [
  http.get('/api/projects', ({ request }) => {
    const url = new URL(request.url);
    const ownerId = url.searchParams.get('ownerId');
    const list = ownerId ? store.filter(p => p.ownerId === ownerId) : store;
    return HttpResponse.json(list);
  }),

  http.get('/api/projects/:id', ({ params }) => {
    const p = store.find(x => x.id === params.id);
    return p ? HttpResponse.json(p) : new HttpResponse(null, { status: 404 });
  }),

  http.post('/api/projects', async ({ request }) => {
    const body = await request.json() as {
      title: string; description: string;
      domain: Domain; customDomain?: string;
      ownerId: string;
      attachments?: Attachment[];
    };
    const newP: Project = {
      id: `p-new-${Date.now()}`,
      title: body.title,
      description: body.description,
      domain: body.domain,
      customDomain: body.customDomain,
      ownerId: body.ownerId,
      status: 'drafting',
      archived: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      attachments: body.attachments ?? [],
    };
    store.push(newP);
    return HttpResponse.json(newP, { status: 201 });
  }),

  // v0.13-B: 更新项目（重命名 / 归档）
  http.patch('/api/projects/:id', async ({ params, request }) => {
    const p = store.find(x => x.id === params.id);
    if (!p) return new HttpResponse(null, { status: 404 });
    const body = await request.json() as { title?: string; archived?: boolean };
    if (body.title !== undefined) p.title = body.title;
    if (body.archived !== undefined) p.archived = body.archived;
    p.updatedAt = new Date().toISOString();
    return HttpResponse.json(p);
  }),

  // v0.13-B: 删除项目
  http.delete('/api/projects/:id', ({ params }) => {
    const idx = store.findIndex(x => x.id === params.id);
    if (idx < 0) return new HttpResponse(null, { status: 404 });
    store.splice(idx, 1);
    return new HttpResponse(null, { status: 204 });
  }),
];
