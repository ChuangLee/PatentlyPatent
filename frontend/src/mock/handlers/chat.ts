import { http, HttpResponse } from 'msw';
import { getCaseAgentScript } from '../fixtures/all_cases';
import { sleep, splitByGrapheme, rand } from '../utils';

export const chatHandlers = [
  http.post('/api/projects/:id/chat', async ({ params, request }) => {
    const { round } = await request.json() as { round: number; userMsg: string };
    const script = getCaseAgentScript(params.id as string, round);

    const stream = new ReadableStream({
      async start(controller) {
        const encoder = new TextEncoder();

        // 1. thinking 信号
        controller.enqueue(encoder.encode('event: thinking\ndata: {}\n\n'));
        await sleep(400);

        // 2. 没有 script 时返回兜底答复
        const text = script?.text
          ?? '抱歉，我没找到对应的预设答复（演示数据未覆盖此轮）。可以让员工继续描述。';

        // 3. 按 grapheme 切 chunk，每 chunk 25-60ms 释放
        for (const chunk of splitByGrapheme(text, 3)) {
          controller.enqueue(encoder.encode(
            `event: delta\ndata: ${JSON.stringify({ chunk })}\n\n`,
          ));
          await sleep(rand(25, 60));
        }

        // 4. 字段更新事件
        controller.enqueue(encoder.encode(
          `event: fields\ndata: ${JSON.stringify({ captured: script?.capturedFields ?? [] })}\n\n`,
        ));

        // 5. done
        controller.enqueue(encoder.encode('event: done\ndata: {}\n\n'));
        controller.close();
      },
    });

    return new HttpResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
    });
  }),
];
