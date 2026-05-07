import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { handlers } from '@/mock/handlers';
import { projectsApi } from '@/api/projects';

const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('projects mock handlers', () => {
  it('GET /projects 返回 3 个 demo case', async () => {
    const list = await projectsApi.list();
    expect(list).toHaveLength(3);
  });

  it('GET /projects/:id 拿到密码学 case', async () => {
    const p = await projectsApi.get('p-crypto-001');
    expect(p.title).toContain('Kyber');
  });

  it('POST /projects 创建新项目并默认 drafting', async () => {
    const p = await projectsApi.create({
      title: '测试', description: 'd', domain: 'other', ownerId: 'u1',
    });
    expect(p.status).toBe('drafting');
    expect(p.id).toMatch(/^p-new-/);
  });

  it('POST /projects/:id/submit 改状态为 submitted', async () => {
    const p = await projectsApi.submit('p-crypto-001');
    expect(p.status).toBe('submitted');
  });

  it('POST /projects/:id/unsubmit 改状态回 reporting', async () => {
    const p = await projectsApi.unsubmit('p-crypto-001');
    expect(p.status).toBe('reporting');
  });
});
