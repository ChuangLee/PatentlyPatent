import { http, HttpResponse } from 'msw';
import type { Role } from '@/types';
import { DEMO_USERS } from '../fixtures/users';

export const authHandlers = [
  http.post('/api/auth/login-as', async ({ request }) => {
    const { role } = await request.json() as { role: Role };
    const user = DEMO_USERS.find(u => u.role === role);
    if (!user) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json(user);
  }),
];
