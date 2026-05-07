import { http, HttpResponse } from 'msw';
import type { Disclosure, ClaimTier } from '@/types';
import { findCase } from '../fixtures/all_cases';

export const disclosureHandlers = [
  http.get('/api/projects/:id/disclosure', ({ params }) => {
    const p = findCase(params.id as string);
    return p?.disclosure
      ? HttpResponse.json(p.disclosure)
      : new HttpResponse(null, { status: 404 });
  }),

  http.put('/api/projects/:id/disclosure', async ({ params, request }) => {
    const body = await request.json() as Partial<Disclosure>;
    const p = findCase(params.id as string);
    if (!p?.disclosure) return new HttpResponse(null, { status: 404 });
    Object.assign(p.disclosure, body);
    return HttpResponse.json(p.disclosure);
  }),

  http.post('/api/projects/:id/disclosure/claim-tier', async ({ params, request }) => {
    const { tier } = await request.json() as { tier: ClaimTier };
    const p = findCase(params.id as string);
    if (!p?.disclosure) return new HttpResponse(null, { status: 404 });
    // mock 行为：把 summary 段重写为对应档（实际代码可以更聪明，这里简单演示）
    const claim = p.disclosure.claims.find(c => c.tier === tier);
    if (claim) {
      p.disclosure.summary = `[已选择${tier}档] ${claim.text}`;
    }
    return HttpResponse.json(p.disclosure);
  }),
];
