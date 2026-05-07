/**
 * 自动挖掘流（auto-mining）
 *
 * 接到 POST /api/projects/:id/auto-mining 后，按节奏流式：
 *   1. thinking（"我先读你的报门..."）
 *   2. delta 进度文字
 *   3. file 事件 spawn 文件到 AI 输出/
 *   4. ... 重复 3 ~ 5 次
 *   5. delta "剩下这几项需要你帮忙补充："
 *   6. delta 列项
 *   7. done
 *
 * 与已有 chat SSE 风格一致，复用前端 consumeSSE。
 */
import { http, HttpResponse } from 'msw';
import type { FileNode, Domain, ProjectStage, ProjectGoal } from '@/types';
import { findCase } from '../fixtures/all_cases';
import { sleep, splitByGrapheme, rand } from '../utils';

let counter = 0;
function nid(): string {
  counter += 1;
  return `aim-${Date.now().toString(36)}-${counter.toString(36)}`;
}

interface MiningContext {
  projectId: string;
  title: string;
  domain: Domain;
  customDomain?: string;
  description: string;
  intake?: { stage: ProjectStage; goal: ProjectGoal; notes?: string };
  // 找到的 AI 输出根 id（用于 spawn 文件用）
  aiRootId: string;
}

/**
 * 基于 ctx 生成 9 项 No.34 模板章节内容（mid-fi 演示版）。
 * 真实生产里这会调 LLM；这里直接拼模板 + 用户描述。
 */
function buildSections(ctx: MiningContext): { name: string; content: string; phase: 'auto' | 'ask' }[] {
  const dom = ctx.customDomain || ({ cryptography: '密码学', infosec: '信息安全', ai: '人工智能' } as Record<string, string>)[ctx.domain] || ctx.domain;
  const desc = ctx.description.trim();
  const stage = ctx.intake?.stage ?? 'idea';
  const stageLabel = { idea: '只是创意', prototype: '已有原型', deployed: '已上线' }[stage];

  return [
    {
      name: '01-背景技术.md',
      phase: 'auto',
      content: `# 一、背景技术（AI 自动初稿）

> 来源：基于你报门描述自动生成；可在 AI 对话区让我修改 / 补充。

## 你描述的技术领域
**${dom}**

## 与本发明最相近似的现有技术
（基于你的描述自动检索同领域已公开方案）

> 演示数据：实际生产会调智慧芽 API / Google Patents 拉真实文献。
> 当前 mid-fi 模式仅给出占位框架。

- [ ] 现有方案 A —— 基于公开论文
- [ ] 现有方案 B —— 基于公开专利
- [ ] 现有方案 C —— 你自己提到的对比基线

## 你报门时的描述（原文）
> ${desc}
`,
    },
    {
      name: '02-现有技术缺点.md',
      phase: 'auto',
      content: `# 二、现有技术的缺点（AI 自动初稿）

> 客观评价现有技术针对本发明优点的不足。

## 推断的现有技术缺点
基于报门描述，本发明针对的痛点可能包括：

- 性能 / 速度限制
- 资源消耗（CPU / 内存 / 带宽）
- 实现复杂度高
- 可扩展性差
- 适配特定场景的能力弱

## 需要你确认
请在右侧文件预览或 AI 对话中告诉我：**你报门里提到的"提升 X%"或"降低 X%" 是相对哪个 baseline？**
`,
    },
    {
      name: '03-技术问题.md',
      phase: 'auto',
      content: `# 三、本发明解决的技术问题或技术目的（AI 自动初稿）

针对第二部分的缺点，本发明要解决的技术问题：

> _基于你的报门描述自动归纳_

${desc}

---

**⚠️ 已知不清楚处**：技术目的的"边界"——是只解决性能问题，还是顺带解决其他维度（如可解释性、可移植性）？请在对话中说明。
`,
    },
    {
      name: '04-技术方案.md',
      phase: 'auto',
      content: `# 四、技术方案的详细阐述（AI 自动初稿 · 待补完）

> 这一节是交底书的核心。AI 已根据你的报门描述拉出**骨架**，但**关键技术细节需要你补充**。

## 总体方案概述
${desc}

## 详细步骤 / 模块（待补）

### 步骤 1：（请描述）
> 输入是什么？输出是什么？关键参数？

### 步骤 2：（请描述）
> ...

### 步骤 3：（请描述）
> ...

## 关键参数 / 阈值（待补）

| 参数 | 取值范围 | 默认值 | 物理含义 |
|---|---|---|---|
| ? | ? | ? | ? |

## 附图说明（如有）
> 如果你有架构图、流程图、时序图，请上传到左侧"我的资料/"。AI 会引用它们。

> 当前阶段：**${stageLabel}**
`,
    },
    {
      name: '05-关键点.md',
      phase: 'auto',
      content: `# 五、本发明的关键点和欲保护点（AI 自动初稿）

提炼自报门描述与第四部分技术方案，AI 列出可能的关键点 / 欲保护点：

1. **核心创新点**：${desc.slice(0, 60)}${desc.length > 60 ? '…' : ''}
2. **辅助创新点 1**：（待 AI 在对话中追问 / 补充）
3. **辅助创新点 2**：（待 AI 在对话中追问 / 补充）

> 注：本节内容会在与你对话过程中逐步细化为三档独权草稿（强 / 中 / 弱）。
`,
    },
    {
      name: '06-优点.md',
      phase: 'auto',
      content: `# 六、相比现有技术的优点（AI 自动初稿）

结合第四部分技术方案，AI 推断本发明可能的优点：

- 性能 / 速度：（请补具体数字）
- 资源消耗：（请补具体数字）
- 可扩展性 / 通用性：（请补）
- 实现成本 / 复杂度：（请补）

> ⚠️ 数字越具体越有利于创造性论证。例如 "在 H100 上吞吐 2.3×" 比 "性能更高" 强一个量级。
`,
    },
    {
      name: '_问题清单.md',  // 这个开头加 _ 表示 "需用户回答" 列表
      phase: 'ask',
      content: `# ❓ 还需要你帮忙的问题清单

AI 已自动填好了 1、2、3、4、5、6 这几节的初稿。下面这几节**只能你自己回答**：

## 七、是否有别的替代方案？
> 同样的发明目的，能否用别的方法实现？比如把 X 替换成 Y，或者用反序的步骤？
> _如果有，请简单描述 1-2 条；这能扩大专利保护范围。_

## 八、是否经过实验、模拟、使用而证明可行？
> - 有实验数据 / 性能基准吗？数字是多少？
> - 在哪种环境 / 数据集上跑的？
> - 与什么 baseline 对比？

## 九、其他有助于代理人理解的资料
> 设计文档 / 论文 / Figma / PPT / 代码片段 …… 都可以传到左侧"我的资料/"。
> 越多越好，AI 会自动分析关联到对应章节。

---

💬 你可以**直接在下方聊天框**回答任意一项，或上传文件后告诉我"看这个"。我会更新对应章节的文件并保存到"AI 输出/"。
`,
    },
  ];
}

export const autoMiningHandlers = [
  http.post('/api/projects/:id/auto-mining', async ({ params, request }) => {
    const projectId = params.id as string;
    const body = await request.json().catch(() => ({})) as Partial<MiningContext>;

    // 试取 demo case 的真实数据；新建项目从 body 里来
    const cse = findCase(projectId);
    const ctx: MiningContext = {
      projectId,
      title: cse?.title ?? body.title ?? '未命名项目',
      domain: cse?.domain ?? body.domain ?? 'other',
      customDomain: cse?.customDomain ?? body.customDomain,
      description: cse?.description ?? body.description ?? '',
      intake: cse?.intake ?? body.intake,
      aiRootId: body.aiRootId ?? 'root-ai',
    };

    const sections = buildSections(ctx);

    const stream = new ReadableStream({
      async start(controller) {
        const enc = new TextEncoder();
        const send = (event: string, data: unknown) =>
          controller.enqueue(enc.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));

        // 1. thinking
        send('thinking', {});
        await sleep(500);

        // 2. opening delta
        const opening = `📋 收到，我先把你的报门描述读一遍...\n\n标题：${ctx.title}\n领域：${ctx.customDomain || ctx.domain}\n\n开始自动挖掘，能写的我直接写好放到 AI 输出/，不清楚的我会列出来请你回答。\n\n`;
        for (const chunk of splitByGrapheme(opening, 3)) {
          send('delta', { chunk });
          await sleep(rand(15, 35));
        }

        // 3. 逐项 spawn 文件
        for (const sec of sections) {
          const intro = sec.phase === 'auto'
            ? `\n✍️ 正在写「${sec.name.replace(/^\d+-|\.md$/g, '').replace(/\.md$/, '')}」...\n`
            : `\n📌 已生成「问题清单」，请看左侧 AI 输出/${sec.name}\n`;
          for (const chunk of splitByGrapheme(intro, 3)) {
            send('delta', { chunk });
            await sleep(rand(15, 35));
          }
          await sleep(300);

          const node: FileNode = {
            id: nid(),
            name: sec.name,
            kind: 'file',
            parentId: ctx.aiRootId,
            source: 'ai',
            mime: 'text/markdown',
            content: sec.content,
            size: new Blob([sec.content]).size,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
          };
          send('file', { node });
          await sleep(450);

          const tick = `   ✓ 已落到 AI 输出/${sec.name}\n`;
          for (const chunk of splitByGrapheme(tick, 3)) {
            send('delta', { chunk });
            await sleep(rand(10, 25));
          }
        }

        // 4. 收尾
        const wrap = `\n✅ 自动挖掘完成。\n\n你看下左侧文件树新冒出来的几个 md 文件——\n  · 1~6 节是 AI 自动写的初稿，可点开右侧预览，有不准的告诉我改\n  · _问题清单.md 是 AI 自己回答不了的几条，挑感兴趣的在下方回答即可\n\n等你确认 / 补充完，我把所有章节合并生成完整的 .docx 交底书放到"AI 输出/专利交底书.docx"。\n`;
        for (const chunk of splitByGrapheme(wrap, 3)) {
          send('delta', { chunk });
          await sleep(rand(15, 30));
        }

        send('done', {});
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
