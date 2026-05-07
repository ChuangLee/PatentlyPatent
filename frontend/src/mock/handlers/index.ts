import { http, HttpResponse } from 'msw';
import { authHandlers } from './auth';
import { projectsHandlers } from './projects';
import { searchHandlers } from './search';
import { disclosureHandlers } from './disclosure';
import { chatHandlers } from './chat';

export const handlers = [
  http.get('/api/ping', () => HttpResponse.json({ ok: true, msg: 'msw working' })),
  ...authHandlers,
  ...projectsHandlers,
  ...searchHandlers,
  ...disclosureHandlers,
  ...chatHandlers,
];
