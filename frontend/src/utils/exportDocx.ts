/**
 * 按 "技术交底书 No.34" 模板生成 docx 并触发浏览器下载。
 *
 * 模板章节（来自 templates/专利技术交底书_No34.doc）：
 *   - 抬头：发明名称、申请类型、发明人/撰写人/联系人、术语解释
 *   一、介绍背景技术（含与本发明最相近似的现有技术方案）
 *   二、现有技术的缺点
 *   三、本发明解决的技术问题或技术目的
 *   四、本发明技术方案的详细阐述
 *   五、本发明的关键点和欲保护点
 *   六、与现有技术相比，本发明的优点
 *   七、是否有别的替代方案
 *   八、是否经过实验、模拟、使用证明可行
 *   九、其他有助于代理人理解的资料
 */
import {
  Document, Paragraph, HeadingLevel, TextRun, Packer, AlignmentType,
} from 'docx';
import type { Project, ClaimTier, Disclosure } from '@/types';

const DOMAIN_LABEL: Record<string, string> = {
  cryptography: '密码学',
  infosec: '信息安全',
  ai: '人工智能',
  other: '其他',
};

const TIER_LABEL: Record<ClaimTier, string> = {
  broad: '宽档', medium: '中档', narrow: '窄档',
};

// ─── helpers ───
function p(text: string, opts: { size?: number; color?: string; bold?: boolean; after?: number } = {}): Paragraph {
  return new Paragraph({
    children: [new TextRun({ text: text ?? '', size: opts.size ?? 22, color: opts.color, bold: opts.bold })],
    spacing: { after: opts.after ?? 160 },
  });
}

function h1(text: string): Paragraph {
  return new Paragraph({
    text, heading: HeadingLevel.HEADING_1,
    spacing: { before: 240, after: 120 },
  });
}

function meta(text: string): Paragraph {
  return new Paragraph({
    children: [new TextRun({ text, size: 18, color: '888888', italics: true })],
    spacing: { after: 80 },
  });
}

function bullet(text: string): Paragraph {
  return new Paragraph({
    children: [new TextRun({ text: '• ' + text, size: 22 })],
    indent: { left: 360 },
    spacing: { after: 80 },
  });
}

/**
 * 按交底书 No.34 章节模板生成 docx。
 * 各章节按 disclosure 字段尽可能填；空字段写"（待 AI 进一步引导填写）"占位。
 */
export async function exportDocx(project: Project, tier: ClaimTier): Promise<void> {
  if (!project.disclosure) {
    throw new Error('当前项目尚无交底书内容（disclosure 为空），无法导出。');
  }
  const d: Disclosure = project.disclosure;
  const claim = d.claims.find(c => c.tier === tier) ?? d.claims[0];
  const allClaims = d.claims;
  const domainLabel = project.customDomain ?? DOMAIN_LABEL[project.domain] ?? project.domain;
  const today = new Date().toLocaleDateString('zh-CN');
  const placeholder = '（待 AI 进一步引导填写）';

  const children: Paragraph[] = [
    // ── 抬头 ──
    new Paragraph({
      text: '技术交底书',
      heading: HeadingLevel.TITLE,
      alignment: AlignmentType.CENTER,
      spacing: { after: 240 },
    }),

    p(`发明名称：${project.title}`, { size: 26, bold: true, after: 120 }),
    p(`申请类型：☑ 发明　　☐ 实用新型　　☐ 外观设计`),
    p(`技术领域：${domainLabel}`),
    p(`本专利发明人：${placeholder}`),
    p(`技术交底书撰写人：（员工）${project.ownerId}`),
    p(`技术问题联系人：${placeholder}`),
    p(`联系人电话：${placeholder}`),
    p(`联系人邮箱：${placeholder}`),
    p(`填写日期：${today}`),

    new Paragraph({ children: [new TextRun({ text: '术语解释：', size: 22, bold: true })], spacing: { before: 240, after: 80 } }),
    p(d.technicalField || placeholder, { size: 20, color: '555555' }),

    // ── 一、背景技术 ──
    h1('一、介绍背景技术，并描述已有的与本发明最相近似的现有技术方案'),
    meta('提示：可多写几个；该现有技术方案在公开出版物上有记载，最好提供出处或专利号。'),
    p(d.background || placeholder),

    // ── 二、现有技术缺点 ──
    h1('二、现有技术的缺点是什么（客观评价）？'),
    meta('提示：客观评价现有技术的缺点是针对本发明的优点来说的。可以从结构、流程等角度推导（成本高、反应速度慢、结构复杂等）。'),
    p(deriveDisadvantages(d) || placeholder),

    // ── 三、本发明解决的技术问题 ──
    h1('三、本发明解决的技术问题或技术目的？'),
    meta('提示：对应现有技术的所有缺点，正面描述本发明要解决的技术问题。'),
    p(d.summary || placeholder),

    // ── 四、技术方案详细阐述 ──
    h1('四、本发明技术方案的详细阐述（即如何解决上述存在的问题）'),
    meta('提示：①核心是说明书公开的技术方案；②每一功能都要有相应的技术实现方案；③应当清楚、完整地描述技术特征及作用、原理。'),
    p(d.embodiments || placeholder),
    ...(d.drawingsDescription
      ? [
          new Paragraph({ children: [new TextRun({ text: '附图说明：', size: 22, bold: true })], spacing: { before: 160, after: 80 } }),
          p(d.drawingsDescription),
        ]
      : []),

    // ── 五、关键点和欲保护点 ──
    h1('五、本发明的关键点和欲保护点'),
    meta('提示：第四条是完整技术方案，本部分是提炼的关键创新点，列 1、2、3…，便于代理人撰写权利要求。'),
    ...allClaims.map((c, i) =>
      p(`${i + 1}. [${TIER_LABEL[c.tier]}] ${c.text}` + (c.risk ? `\n   ⚠ 风险：${c.risk}` : '')),
    ),
    p(`本次导出选定档位：${TIER_LABEL[tier]}（${claim?.text || placeholder}）`, { color: '1677ff', bold: true }),

    // ── 六、相比现有技术的优点 ──
    h1('六、与第一条所述的最好的现有技术相比，本发明有何优点（简单介绍）？'),
    meta('提示：结合技术方案分条描述，以推理方式说明，做到有理有据；可对应第三条要解决的问题。'),
    p(deriveAdvantages(d) || placeholder),

    // ── 七、替代方案 ──
    h1('七、针对第四部分中的技术方案，是否还有别的替代方案同样能实现发明目的？'),
    meta('提示：拓展思路可以是部分结构、器件、方法步骤的替代，也可以是完整方案的替代。'),
    p(deriveAlternatives(allClaims) || placeholder),

    // ── 八、实验/模拟/使用 ──
    h1('八、本发明是否经过实验、模拟、使用而证明可行，结果如何？'),
    meta('提示：如果有，请简单说明并表述结果或效果即可。'),
    p(deriveExperiments(d) || placeholder),

    // ── 九、其他资料 ──
    h1('九、其他有助于专利代理人理解本技术的资料'),
    meta('提示：技术文档、说明书等，可帮助代理人更快完成申请文件撰写。'),
    p((project.attachments?.length ?? 0) > 0
        ? `已上传 ${project.attachments!.length} 项辅助资料；详见项目工作台 "我的资料/" 文件夹。`
        : placeholder),
    ...(project.attachments?.map(a => bullet(`${a.name}${a.url ? ` （${a.url}）` : ''}`)) ?? []),

    // ── 末尾 ──
    new Paragraph({ spacing: { before: 360 } }),
    new Paragraph({
      children: [new TextRun({ text: '────────────────────', size: 18, color: '888888' })],
      alignment: AlignmentType.CENTER,
    }),
    new Paragraph({
      children: [new TextRun({
        text: `本文档由 PatentlyPatent 自动生成 · 项目 ${project.id} · ${new Date().toLocaleString('zh-CN', { hour12: false })}`,
        size: 16, color: '888888', italics: true,
      })],
      alignment: AlignmentType.CENTER,
    }),
  ];

  const doc = new Document({
    creator: 'PatentlyPatent',
    title: project.title,
    description: '专利技术交底书（按 No.34 模板）',
    sections: [{ children }],
  });

  const blob = await Packer.toBlob(doc);
  const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  const filename = `${project.title}_交底书_${ts}.docx`;

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ─── 章节内容推导：从 disclosure 字段推断 No.34 模板新章节内容 ───
// disclosure 现有字段是 v1 设计，与 No.34 模板有部分重合；新模板章节没显式字段时
// 用 heuristic 派生或留 placeholder。

function deriveDisadvantages(d: Disclosure): string {
  // 目前 background 段往往含"现有技术缺点"描述，截取或追问
  const bg = d.background ?? '';
  const m = bg.match(/(缺点|不足|存在|瓶颈|挑战|限制)[^。]*[。.]/g);
  return m ? m.join('') : '';
}

function deriveAdvantages(d: Disclosure): string {
  // summary 段一般含"效果""优势""提升"
  const s = d.summary ?? '';
  const m = s.match(/(优势|优点|效果|提升|改进|降低|减少|加快|节省|更优)[^。]*[。.]/g);
  return m ? m.join('') : '';
}

function deriveAlternatives(claims: Disclosure['claims']): string {
  if (claims.length <= 1) return '';
  // 三档独权可视作"替代/拓展方案"
  return claims
    .map((c, i) => `方案 ${i + 1}（${TIER_LABEL[c.tier]}）：${c.text}`)
    .join('\n');
}

function deriveExperiments(d: Disclosure): string {
  // embodiments 中常含数据/实验
  const e = d.embodiments ?? '';
  const m = e.match(/(实验|测试|实测|验证|对比|结果|数据|提升|降低)[^。]*[。.]/g);
  return m ? m.join('') : '';
}
