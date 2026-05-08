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

// v0.18-C: 结构化消息类型，'text' 是默认（兼容历史数据）
export type ChatMessageType = 'text' | 'tool_call' | 'thinking' | 'error';

export interface ChatMessage {
  id: string;
  role: 'agent' | 'user';
  content: string;
  ts: string;
  type?: ChatMessageType;            // 默认 'text'，老数据无此字段
  tool?: {
    name: string;
    input: unknown;
    id?: string;
    result?: string;
    data?: unknown;
    t0?: number;            // v0.20: 开始时间 (Date.now() ms)
    tDurationMs?: number;   // v0.20: 工具耗时 (ms)
  };
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
  customDomain?: string;                // domain==='other' 时填，自由文本
  description: string;
  status: ProjectStatus;
  archived?: boolean;
  ownerId: string;
  createdAt: string;
  updatedAt: string;
  attachments?: Attachment[];           // 旧字段，逐步迁入 fileTree
  intake?: IntakeAnswers;               // 报门时回答的关键问题
  fileTree?: FileNode[];                // 项目文件树（mid-fi mock 全在前端）
  miningSummary?: MiningSummary;
  searchReport?: SearchReport;
  disclosure?: Disclosure;
}

// 文件树节点
export type FileNodeKind = 'folder' | 'file';
export type FileSource = 'user' | 'ai' | 'system' | 'kb';   // v0.22: kb=只读专利知识库
export type FileMime =
  | 'text/markdown'
  | 'text/plain'
  | 'application/json'
  | 'image/png' | 'image/jpeg' | 'image/svg+xml'
  | 'application/pdf'
  | 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' // docx
  | 'text/x-link'
  | 'text/html'
  | string;                                           // kb 节点 mime 来自后端 mimetypes，宽松

export interface FileNode {
  id: string;
  name: string;
  kind: FileNodeKind;
  parentId: string | null;          // 根节点 null
  source: FileSource;
  hidden?: boolean;                 // .ai-internal/ 等隐藏文件夹默认 true
  mime?: FileMime;
  size?: number;
  content?: string;                 // 内联文本内容（md/txt/json）
  url?: string;                     // 外链 / 占位下载
  kbPath?: string;                  // v0.22: source='kb' 时的相对路径（懒加载用）
  createdAt: string;
  updatedAt: string;
}

// 报门关键问题答案（3 个）
export type ProjectStage = 'idea' | 'prototype' | 'deployed';
export type ProjectGoal = 'search_only' | 'full_disclosure' | 'specific_section';

export interface IntakeAnswers {
  stage: ProjectStage;            // 创意 / 原型 / 已落地
  goal: ProjectGoal;              // 期望产出
  notes?: string;                 // 自由补充
}

// SSE 事件类型
export type ChatStreamEvent =
  | { type: 'thinking'; text?: string }
  | { type: 'delta'; chunk: string }
  | { type: 'fields'; captured: string[] }
  | { type: 'file'; node: FileNode }
  // v0.17-D: agent SDK 扩展事件（spike endpoint 用）
  | { type: 'tool_use'; name: string; input: Record<string, unknown>; id?: string }
  | { type: 'tool_result'; text: string; data?: unknown }
  | { type: 'error'; message: string }
  | { type: 'done'; stop_reason?: string; mock?: boolean };
