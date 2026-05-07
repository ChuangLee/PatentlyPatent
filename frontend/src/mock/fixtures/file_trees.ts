/**
 * 三个 demo case 的初始 fileTree。
 * 包含：我的资料/（用户假上传）、AI 输出/（已生成 md/docx）、.ai-internal/（隐藏 checkpoint）
 */
import type { FileNode, IntakeAnswers } from '@/types';

const T_BASE = '2026-05-01T09:00:00Z';

function ms() {
  return new Date().toISOString();
}

// ─── 密码学 case ───
const cryptoSearchReportMd = `# 现有技术检索报告 · Kyber-512 NTT 优化

> 自动生成 · 共 8 篇命中文献
> 4 档专利性结论：**moderate**（边缘）

## 摘要
本申请相对 PQClean 标量参考实现 38% 提升，但 EP3863215A1（Infineon, word-level 并行）与本案手段有相似处。
建议补充 pqm4 与 word-level 并行的对比实验，论证 SIMD 向量化的非显而易见性。

## X/Y/N 分布
- 0 X 类（破新颖）
- 3 Y 类（创造性结合可能击破）
- 5 N 类（不相关）

## 关键 Y 类文献

### 1. CN114444128A · 中国电信
基于 Kyber 框架的密钥封装方法，对 NTT 进行标量优化。
**与本申请对照**：
- 问题：类似
- 手段：标量优化 vs 本案 SIMD 向量化
- 效果：提升 12% vs 本案 38%

### 2. EP3863215A1 · Infineon
NTT acceleration via word-level parallelism on 32-bit ARM cores。
**与本申请对照**：
- 问题：相同
- 手段：word-level 并行
- 效果：提升 22%

### 3. arXiv:2110.10377 · CHES 2021
对 pqm4 的 Cortex-M4 Kyber 进一步内联汇编优化。
**与本申请对照**：
- 问题：相同
- 手段：内联汇编优化
- 效果：提升 18%

---

> 演示数据 · 仅供原型展示
`;

const cryptoMiningMd = `# 创新点拆解 · 密码学 case

## 五要素
| 维度 | 内容 |
|---|---|
| **领域** | 后量子密码 / Kyber-512 / NTT / ARM Cortex-M4 |
| **问题** | NTT 在嵌入式平台速度瓶颈；PQClean 标量实现性能不足 |
| **手段** | SIMD 向量化；NTT 蝶形运算两路并行；32-bit word 通道并行 |
| **效果** | 密钥封装快 38%；代码体积 +1.8KB |
| **区别现有** | 只动 NTT 不联动其他子模块；相对 PQClean 标量基线 |

## 三档独权概括度

### 强档（broad）
> 一种 Kyber-512 KEM 实现方法，其特征在于对 NTT 子运算进行向量化并行处理。

⚠️ **风险**：上位过激，可能被 EP3863215A1 word-level 并行破创造性

### 中档（medium）— 推荐
> 一种 Kyber-512 KEM 实现方法，包括：在 ARM Cortex-M4 上对 NTT 蝶形运算执行 SIMD 两路并行；保持 Compression 和 SHAKE 子模块不变；其特征在于密钥封装速度相对标量参考提升至少 30%。

✅ 稳妥

### 弱档（narrow）
> 限定 SIMD 通道宽度为 32-bit、并行路数为 2、目标平台为 ARM Cortex-M4，相对 PQClean v1.x 提升 38%、代码体积增量 1.8KB。

✅ 紧贴实施例，确定性高
`;

const cryptoIntake: IntakeAnswers = {
  stage: 'prototype',
  goal: 'full_disclosure',
  notes: '已有 STM32L4 demo，相对 PQClean 1.0.0 测得稳定 38% 提升',
};

const cryptoTree: FileNode[] = [
  // root folders
  { id: 'cr-root-user', name: '我的资料', kind: 'folder', parentId: null, source: 'user', createdAt: T_BASE, updatedAt: T_BASE },
  { id: 'cr-root-ai',   name: 'AI 输出',   kind: 'folder', parentId: null, source: 'ai',   createdAt: T_BASE, updatedAt: T_BASE },
  { id: 'cr-root-int',  name: '.ai-internal', kind: 'folder', parentId: null, source: 'system', hidden: true, createdAt: T_BASE, updatedAt: T_BASE },

  // 我的资料/
  { id: 'cr-u-1', name: '设计文档.md', kind: 'file', parentId: 'cr-root-user', source: 'user',
    mime: 'text/markdown', size: 4321, createdAt: T_BASE, updatedAt: T_BASE,
    content: '# Kyber-512 NTT 优化 · 内部设计文档\n\n## 目标\n在 STM32L4 上把密钥封装时间从 12.4ms 降到 < 8ms。\n\n## 方案\nNTT 蝶形运算两路 SIMD 向量化，保持其他子模块不变。\n\n（演示数据）' },
  { id: 'cr-u-2', name: 'pqclean-baseline.png', kind: 'file', parentId: 'cr-root-user', source: 'user',
    mime: 'image/png', size: 12450, url: 'https://placehold.co/640x360/png?text=PQClean+Baseline+Bench',
    createdAt: T_BASE, updatedAt: T_BASE },
  { id: 'cr-u-3', name: 'NIST PQC 标准化网站', kind: 'file', parentId: 'cr-root-user', source: 'user',
    mime: 'text/x-link', url: 'https://csrc.nist.gov/projects/post-quantum-cryptography',
    createdAt: T_BASE, updatedAt: T_BASE },

  // AI 输出/
  { id: 'cr-a-1', name: '现有技术检索报告.md', kind: 'file', parentId: 'cr-root-ai', source: 'ai',
    mime: 'text/markdown', content: cryptoSearchReportMd, createdAt: T_BASE, updatedAt: T_BASE },
  { id: 'cr-a-2', name: '创新点拆解.md', kind: 'file', parentId: 'cr-root-ai', source: 'ai',
    mime: 'text/markdown', content: cryptoMiningMd, createdAt: T_BASE, updatedAt: T_BASE },
  { id: 'cr-a-3', name: '专利交底书.docx', kind: 'file', parentId: 'cr-root-ai', source: 'ai',
    mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    size: 18432, url: '#export-docx', createdAt: T_BASE, updatedAt: T_BASE },

  // .ai-internal/
  { id: 'cr-i-1', name: 'mining-checkpoint.json', kind: 'file', parentId: 'cr-root-int', source: 'system',
    mime: 'application/json',
    content: JSON.stringify({ stage: 'completed', stepsDone: ['extract','search','classify','draft'], at: T_BASE }, null, 2),
    createdAt: T_BASE, updatedAt: T_BASE },
];

// ─── 信息安全 case ───
const infosecSearchReportMd = `# 现有技术检索报告 · API 网关多信号融合

> 4 档专利性结论：**strong**（很可能新颖）

## 摘要
在 z-score 单一信号 + GBDT 单分类基础上，本案的多信号决策融合 + 自适应阈值无现有技术覆盖，
新颖性创造性都强。建议加快撰写。

## X/Y/N 分布：0 X / 2 Y / 6 N

> 演示数据`;

const infosecMiningMd = `# 创新点拆解 · 信息安全

| 维度 | 内容 |
|---|---|
| 领域 | API 网关 / UEBA / 异常检测 |
| 问题 | 单信号检测误报率高 |
| 手段 | z-score 统计 + GBDT 机器学习 + 滑动窗口三路融合 |
| 效果 | 误报率降 40% |
| 区别现有 | 多信号决策融合 + 自适应阈值（先前文献仅单信号） |
`;

const infosecIntake: IntakeAnswers = {
  stage: 'deployed',
  goal: 'full_disclosure',
  notes: '已上线 6 个月，误报率验证降 40%',
};

const infosecTree: FileNode[] = [
  { id: 'is-root-user', name: '我的资料', kind: 'folder', parentId: null, source: 'user', createdAt: T_BASE, updatedAt: T_BASE },
  { id: 'is-root-ai',   name: 'AI 输出',   kind: 'folder', parentId: null, source: 'ai',   createdAt: T_BASE, updatedAt: T_BASE },
  { id: 'is-root-int',  name: '.ai-internal', kind: 'folder', parentId: null, source: 'system', hidden: true, createdAt: T_BASE, updatedAt: T_BASE },

  { id: 'is-u-1', name: 'gateway-arch.png', kind: 'file', parentId: 'is-root-user', source: 'user',
    mime: 'image/png', url: 'https://placehold.co/800x500/png?text=API+Gateway+Architecture',
    size: 23410, createdAt: T_BASE, updatedAt: T_BASE },
  { id: 'is-u-2', name: '上线后误报率周报.md', kind: 'file', parentId: 'is-root-user', source: 'user',
    mime: 'text/markdown', size: 1820, createdAt: T_BASE, updatedAt: T_BASE,
    content: '# 上线后误报率周报\n\n| 周次 | 误报率 |\n|---|---|\n| W1 | 6.8% |\n| W4 | 4.2% |\n| W12 | 4.0% |\n\n相比 baseline z-score 单信号方案的 6.7%，整体降低 ≈ 40%。\n\n（演示数据）' },

  { id: 'is-a-1', name: '现有技术检索报告.md', kind: 'file', parentId: 'is-root-ai', source: 'ai',
    mime: 'text/markdown', content: infosecSearchReportMd, createdAt: T_BASE, updatedAt: T_BASE },
  { id: 'is-a-2', name: '创新点拆解.md', kind: 'file', parentId: 'is-root-ai', source: 'ai',
    mime: 'text/markdown', content: infosecMiningMd, createdAt: T_BASE, updatedAt: T_BASE },
  { id: 'is-a-3', name: '专利交底书.docx', kind: 'file', parentId: 'is-root-ai', source: 'ai',
    mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    url: '#export-docx', size: 21560, createdAt: T_BASE, updatedAt: T_BASE },

  { id: 'is-i-1', name: 'mining-checkpoint.json', kind: 'file', parentId: 'is-root-int', source: 'system',
    mime: 'application/json',
    content: JSON.stringify({ stage: 'completed', stepsDone: ['extract','search','classify','draft'] }, null, 2),
    createdAt: T_BASE, updatedAt: T_BASE },
];

// ─── AI case（drafting） ───
const aiSearchReportMd = `# 现有技术检索报告 · LLM KV-cache 分页

> 4 档专利性结论：**weak**（创造性存疑） · ⚠️ 不建议作为独权直接申请

## 关键发现
**vLLM PagedAttention（SOSP 2023, arXiv:2309.06180）已公开 KV-cache 分页核心思想**。
作为独权将被 X 类破新颖。

## X/Y/N 分布：**2 X** / 3 Y / 3 N

## 建议
缩窄到具体的"非首推用户场景下的优先级调度策略"，或本人放弃申请。
`;

const aiMiningMd = `# 创新点拆解 · AI 推理批处理

| 维度 | 内容 |
|---|---|
| 领域 | LLM 推理 / 批处理 / 调度 |
| 问题 | 单 GPU 推理吞吐瓶颈 |
| 手段 | KV-cache 分页 + 优先级请求调度 |
| 效果 | 吞吐 2.3× |
| 区别现有 | ⚠️ KV-cache 分页 = vLLM PagedAttention，已公开 |

## 结论
强烈建议本案聚焦到"非首推用户场景的优先级调度"等具体新增策略。
`;

const aiIntake: IntakeAnswers = {
  stage: 'prototype',
  goal: 'search_only',
  notes: '想先确认是否值得申请',
};

const aiTree: FileNode[] = [
  { id: 'ai-root-user', name: '我的资料', kind: 'folder', parentId: null, source: 'user', createdAt: T_BASE, updatedAt: T_BASE },
  { id: 'ai-root-ai',   name: 'AI 输出',   kind: 'folder', parentId: null, source: 'ai',   createdAt: T_BASE, updatedAt: T_BASE },
  { id: 'ai-root-int',  name: '.ai-internal', kind: 'folder', parentId: null, source: 'system', hidden: true, createdAt: T_BASE, updatedAt: T_BASE },

  { id: 'ai-u-1', name: 'inference-bench.md', kind: 'file', parentId: 'ai-root-user', source: 'user',
    mime: 'text/markdown', size: 1450, createdAt: T_BASE, updatedAt: T_BASE,
    content: '# 推理性能基准\n\n单 H100 上：\n- baseline: 8 req/s\n- 本方案: 18.4 req/s（2.3×）\n\n（演示数据）' },

  { id: 'ai-a-1', name: '现有技术检索报告.md', kind: 'file', parentId: 'ai-root-ai', source: 'ai',
    mime: 'text/markdown', content: aiSearchReportMd, createdAt: T_BASE, updatedAt: T_BASE },
  { id: 'ai-a-2', name: '创新点拆解.md', kind: 'file', parentId: 'ai-root-ai', source: 'ai',
    mime: 'text/markdown', content: aiMiningMd, createdAt: T_BASE, updatedAt: T_BASE },
  // AI case 还在 drafting，没出最终交底书

  { id: 'ai-i-1', name: 'mining-checkpoint.json', kind: 'file', parentId: 'ai-root-int', source: 'system',
    mime: 'application/json',
    content: JSON.stringify({ stage: 'reporting', stepsDone: ['extract','search','classify'], blocked: 'weak_novelty' }, null, 2),
    createdAt: T_BASE, updatedAt: T_BASE },
];

export const FILE_TREES: Record<string, FileNode[]> = {
  'p-crypto-001':  cryptoTree,
  'p-infosec-001': infosecTree,
  'p-ai-001':      aiTree,
};

export const INTAKE_ANSWERS: Record<string, IntakeAnswers> = {
  'p-crypto-001':  cryptoIntake,
  'p-infosec-001': infosecIntake,
  'p-ai-001':      aiIntake,
};

export { ms };
