// 角色
export type Role = 'employee' | 'admin';

// 项目状态机（v0.2 简化：删 submitted，员工导出 docx 后由本人决定后续）
export type ProjectStatus = 'drafting' | 'researching' | 'reporting' | 'completed';

// 报门时上传的资料（多种）
export type AttachmentType = 'file' | 'link' | 'note';

export interface Attachment {
  id: string;
  type: AttachmentType;
  name: string;            // 文件名 / 链接标题 / note 摘要
  size?: number;           // file 类型字节数
  mime?: string;           // file 类型 MIME
  url?: string;            // link 类型 URL
  content?: string;        // note 类型纯文本
  addedAt: string;         // ISO
}

// 技术领域
export type Domain = 'cryptography' | 'infosec' | 'ai' | 'other';

// 4 档专利性结论
export type Patentability = 'strong' | 'moderate' | 'weak' | 'not_recommended';

// 三档独权概括度
export type ClaimTier = 'broad' | 'medium' | 'narrow';

// 命中文献 X/Y/N 标注
export type XYNTag = 'X' | 'Y' | 'N';

export interface User {
  id: string;
  name: string;
  role: Role;
  department: string;
  avatar?: string;
}

export interface ChatMessage {
  id: string;
  role: 'agent' | 'user';
  content: string;
  ts: string;
  meta?: {
    stage?: '5why' | 'whatif' | 'generalize' | 'effect';
    capturedFields?: string[];
  };
}

export interface MiningSummary {
  field: string[];
  problem: string[];
  means: string[];
  effect: string[];
  differentiator: string[];
  conversation: ChatMessage[];
}

export interface PriorArtHit {
  id: string;
  title: string;
  abstract: string;
  applicant: string;
  pubDate: string;
  ipc: string[];
  xyn: XYNTag;
  comparison: { problem: string; means: string; effect: string };
  url?: string;
}

export interface SearchReport {
  patentability: Patentability;
  rationale: string;
  hits: PriorArtHit[];
}

export interface Disclosure {
  technicalField: string;
  background: string;
  summary: string;
  claims: { tier: ClaimTier; text: string; risk: string }[];
  drawingsDescription: string;
  embodiments: string;
  bodyMarkdown: string;
}

export interface Project {
  id: string;
  title: string;
  domain: Domain;
  description: string;
  status: ProjectStatus;
  ownerId: string;
  createdAt: string;
  updatedAt: string;
  attachments?: Attachment[];           // 报门时上传的资料
  miningSummary?: MiningSummary;
  searchReport?: SearchReport;
  disclosure?: Disclosure;
}

// SSE 事件类型
export type ChatStreamEvent =
  | { type: 'thinking' }
  | { type: 'delta'; chunk: string }
  | { type: 'fields'; captured: string[] }
  | { type: 'done' };
