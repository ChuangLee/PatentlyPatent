import { http, HttpResponse } from 'msw';
import { findCase } from '../fixtures/all_cases';
import { sleep } from '../utils';

export const searchHandlers = [
  http.post('/api/projects/:id/search', async ({ params }) => {
    await sleep(800); // 模拟检索耗时
    const p = findCase(params.id as string);
    if (!p?.searchReport) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json(p.searchReport);
  }),
];
