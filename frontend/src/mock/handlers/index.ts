import { http, HttpResponse } from 'msw';

// 占位 handlers，Task 7-8 会扩充
export const handlers = [
  http.get('/api/ping', () =>
    HttpResponse.json({ ok: true, msg: 'msw working' })
  ),
];
