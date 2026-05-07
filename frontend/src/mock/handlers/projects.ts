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
      title: string; description: string; domain: Domain; ownerId: string;
      attachments?: Attachment[];
    };
    const newP: Project = {
      id: `p-new-${Date.now()}`,
      title: body.title,
      description: body.description,
      domain: body.domain,
      ownerId: body.ownerId,
      status: 'drafting',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      attachments: body.attachments ?? [],
    };
    store.push(newP);
    return HttpResponse.json(newP, { status: 201 });
  }),
];
