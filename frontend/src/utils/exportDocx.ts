import {
  Document,
  Paragraph,
  HeadingLevel,
  TextRun,
  Packer,
  AlignmentType,
} from 'docx';
import type { Project, ClaimTier, Disclosure } from '@/types';

const DOMAIN_LABEL: Record<string, string> = {
  cryptography: '密码学',
  infosec: '信息安全',
  ai: '人工智能',
  other: '其他',
};

const TIER_LABEL: Record<ClaimTier, string> = {
  broad: '宽档',
  medium: '中档',
  narrow: '窄档',
};

function bodyParagraph(text: string): Paragraph {
  return new Paragraph({
    children: [new TextRun({ text: text ?? '', size: 24 })],
    spacing: { after: 160 },
  });
}

function heading(text: string): Paragraph {
  return new Paragraph({
    text,
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 240, after: 120 },
  });
}

function smallMeta(text: string): Paragraph {
  return new Paragraph({
    children: [new TextRun({ text, size: 18, color: '888888' })],
    alignment: AlignmentType.LEFT,
    spacing: { before: 120 },
  });
}

/**
 * 生成 docx 并触发浏览器下载
 * @param project 项目（含 disclosure）
 * @param tier   用户所选独权档
 */
export async function exportDocx(project: Project, tier: ClaimTier): Promise<void> {
  if (!project.disclosure) {
    throw new Error('当前项目尚无交底书内容（disclosure 为空），无法导出。');
  }
  const d: Disclosure = project.disclosure;
  const claim = d.claims.find(c => c.tier === tier) ?? d.claims[0];

  const children: Paragraph[] = [
    new Paragraph({
      text: project.title,
      heading: HeadingLevel.TITLE,
      alignment: AlignmentType.CENTER,
      spacing: { after: 240 },
    }),

    heading('一、技术领域'),
    bodyParagraph(d.technicalField),

    heading('二、背景技术'),
    bodyParagraph(d.background),

    heading('三、发明内容'),
    bodyParagraph(d.summary),

    heading(`四、权利要求书（${TIER_LABEL[tier]}独权）`),
    bodyParagraph(claim?.text ?? ''),
    bodyParagraph(`风险提示：${claim?.risk ?? ''}`),

    heading('五、附图说明'),
    bodyParagraph(d.drawingsDescription),

    heading('六、具体实施方式'),
    bodyParagraph(d.embodiments),

    smallMeta(
      `项目 id: ${project.id} · 领域: ${DOMAIN_LABEL[project.domain] ?? project.domain} · ` +
      `创建时间: ${new Date(project.createdAt).toLocaleString('zh-CN', { hour12: false })}`,
    ),
    smallMeta('由 PatentlyPatent 生成'),
  ];

  const doc = new Document({
    creator: 'PatentlyPatent',
    title: project.title,
    sections: [{ children }],
  });

  const blob = await Packer.toBlob(doc);
  const ts = new Date()
    .toISOString()
    .replace(/[-:T]/g, '')
    .slice(0, 14); // YYYYMMDDHHmmss
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
