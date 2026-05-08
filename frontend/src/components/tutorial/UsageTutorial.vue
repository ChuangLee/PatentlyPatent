<script setup lang="ts">
/**
 * v0.26 使用教程组件
 * - 6 步完整流程演示
 * - 静态示意图 + 假数据卡片，不引入 store / API
 * - 由 DefaultLayout 的 a-modal 包裹
 */
defineEmits<{
  (e: 'start'): void;
  (e: 'skip'): void;
}>();

interface Step {
  no: number;
  title: string;
  desc: string;
  emoji: string;
  kind:
    | 'report'
    | 'timeline'
    | 'agent'
    | 'filetree'
    | 'qa'
    | 'export';
}

const steps: Step[] = [
  {
    no: 1,
    title: '报门 · 提交创意',
    emoji: '💡 → 📝',
    desc:
      '在 Dashboard 点「✨ 新建报门」按钮，填写标题、技术领域、阶段、期望，并可拖拽上传背景资料（论文/原型代码/PPT）。',
    kind: 'report',
  },
  {
    no: 2,
    title: '工作台 · 5 步 timeline',
    emoji: '⚡',
    desc:
      '进入项目工作台后，顶部 5 步 timeline 显示挖掘进度。点「⚡ 一键全程挖掘」让 agent 自动跑完所有节，或一步步对话引导。',
    kind: 'timeline',
  },
  {
    no: 3,
    title: 'Agent 自驱挖掘',
    emoji: '🤖',
    desc:
      'agent 自动调用 7 个工具：智慧芽检索、年度趋势、申请人排名、法律状态、文件搜索…遇到重要专利会自动保存到「📁 AI 输出/调研下载/类似专利/」。',
    kind: 'agent',
  },
  {
    no: 4,
    title: '文件树 · 三类产物',
    emoji: '📁',
    desc:
      '左侧文件树展示项目所有产物 — 我的资料/（你上传的）、AI 输出/（agent 生成）、📚 专利知识/（419 文件只读知识库）。点击文件右栏预览。',
    kind: 'filetree',
  },
  {
    no: 5,
    title: '答问回填 · 让交底书更准',
    emoji: '💬',
    desc:
      'agent 会在 chat 区主动问关键问题（核心思想、关键步骤、效果数据等），你的回答会被自动写回对应章节 .md 文件。',
    kind: 'qa',
  },
  {
    no: 6,
    title: '导出 .docx 交底书',
    emoji: '📄 → 📥',
    desc:
      '所有节挖掘完成后，工作台「导出」按钮一键生成 No.34 模板的 .docx 交底书，可直接交给专利代理人或专利委员会。',
    kind: 'export',
  },
];

// Step 2 静态 timeline 数据
const fakeStages = [
  { title: '需求理解', status: 'finish' as const },
  { title: '现有技术检索', status: 'finish' as const },
  { title: '差异分析', status: 'finish' as const },
  { title: '权利要求拟定', status: 'process' as const },
  { title: '交底书生成', status: 'wait' as const },
];

// Step 3 静态 tool_call 卡片
const fakeToolCalls = [
  {
    tool: 'search_patents',
    args: 'q="区块链 供应链 溯源" & date>=2018',
    result: '命中 2,458 件，TOP 国家：CN 1,820 / US 412 / JP 134',
  },
  {
    tool: 'search_applicants',
    args: 'q="区块链 供应链"',
    result: 'IBM (387) · 阿里巴巴 (296) · 腾讯 (184) · 京东 (132)',
  },
  {
    tool: 'get_year_trend',
    args: 'q="区块链 供应链 溯源"',
    result: '2018: 124 → 2020: 478 → 2022: 612 → 2024: 543（趋稳）',
  },
  {
    tool: 'save_research',
    args: 'pid=CN112367164B',
    result: '已保存到 AI 输出/调研下载/类似专利/CN112367164B.md',
  },
];

// Step 4 静态文件树
interface FT {
  name: string;
  icon: string;
  children?: FT[];
}
const fakeTree: FT[] = [
  {
    name: '我的资料',
    icon: '📁',
    children: [
      { name: '原型架构图.png', icon: '🖼️' },
      { name: '初稿.md', icon: '📄' },
    ],
  },
  {
    name: 'AI 输出',
    icon: '📁',
    children: [
      {
        name: '调研下载',
        icon: '📁',
        children: [
          { name: '类似专利', icon: '📁' },
          { name: '年度趋势.md', icon: '📊' },
        ],
      },
      { name: '权利要求草稿.md', icon: '📄' },
    ],
  },
  {
    name: '📚 专利知识 (只读)',
    icon: '📁',
    children: [
      { name: 'CNIPA 审查指南.md', icon: '📄' },
      { name: '撰写规范.md', icon: '📄' },
      { name: '… 419 个文件', icon: '🗃️' },
    ],
  },
];

// Step 5 静态对话
const fakeQA = [
  { who: 'agent', text: '请用一句话描述发明的核心思想是什么？（不超过 100 字）' },
  {
    who: 'user',
    text:
      '通过零知识证明压缩供应链节点的多方签名，使中间环节可以不暴露原始数据即可验证溯源链路完整性。',
  },
  { who: 'agent', text: '已写回到「03_权利要求.md - §1 概述」。继续追问：关键加密步骤的输入输出是？' },
];

const exportFileName = '区块链供应链溯源_交底书_2026-05-08.docx';
</script>

<template>
  <div class="pp-tut">
    <header class="pp-tut__hero">
      <div class="pp-tut__hero-text">
        <h2 class="pp-tut__hero-title">从一个想法到一份交底书 · 6 步走完</h2>
        <p class="pp-tut__hero-sub">
          PatentlyPatent 把员工 + AI agent 串成一条流水线：你提想法 → agent 检索 + 拟稿 → 你答关键问题 → 一键导出
          .docx。下面用一个示例项目「区块链供应链溯源」演示完整流程。
        </p>
      </div>
      <div class="pp-tut__hero-emoji">🚀</div>
    </header>

    <section
      v-for="s in steps"
      :key="s.no"
      class="pp-tut__step"
      :data-step="s.no"
    >
      <div class="pp-tut__step-head">
        <span class="pp-tut__step-no">Step {{ s.no }}</span>
        <span class="pp-tut__step-title">{{ s.title }}</span>
        <span class="pp-tut__step-emoji">{{ s.emoji }}</span>
      </div>
      <p class="pp-tut__step-desc">{{ s.desc }}</p>

      <!-- ============== 各步演示区 ============== -->

      <!-- Step 1：报门表单静态卡 -->
      <div v-if="s.kind === 'report'" class="pp-tut__demo pp-tut__demo--form">
        <div class="pp-tut__form-card">
          <div class="pp-tut__form-row">
            <label>标题</label>
            <div class="pp-tut__form-val">区块链供应链溯源</div>
          </div>
          <div class="pp-tut__form-row">
            <label>技术领域</label>
            <div class="pp-tut__form-val">
              <span class="pp-tut__chip pp-tut__chip--primary">信息安全</span>
            </div>
          </div>
          <div class="pp-tut__form-row">
            <label>阶段</label>
            <div class="pp-tut__form-val">
              <span class="pp-tut__chip">🛠️ 已有原型 / Demo</span>
            </div>
          </div>
          <div class="pp-tut__form-row">
            <label>期望产出</label>
            <div class="pp-tut__form-val">
              <span class="pp-tut__chip pp-tut__chip--primary">完整专利交底书 (.docx)</span>
            </div>
          </div>
          <div class="pp-tut__form-row">
            <label>资料附件</label>
            <div class="pp-tut__form-val pp-tut__form-files">
              <span>📎 原型架构图.png</span>
              <span>📎 初稿.md</span>
              <span>📎 性能对比.csv</span>
            </div>
          </div>
          <div class="pp-tut__form-foot">
            <span class="pp-tut__form-btn pp-tut__form-btn--primary">提交报门</span>
          </div>
        </div>
      </div>

      <!-- Step 2：5 步 timeline -->
      <div v-else-if="s.kind === 'timeline'" class="pp-tut__demo">
        <div class="pp-tut__timeline">
          <div
            v-for="(stg, i) in fakeStages"
            :key="i"
            class="pp-tut__stage"
            :class="`pp-tut__stage--${stg.status}`"
          >
            <div class="pp-tut__stage-dot">
              <span v-if="stg.status === 'finish'">✓</span>
              <span v-else-if="stg.status === 'process'" class="pp-tut__pulse" />
              <span v-else>{{ i + 1 }}</span>
            </div>
            <div class="pp-tut__stage-text">
              <div class="pp-tut__stage-title">{{ stg.title }}</div>
              <div class="pp-tut__stage-status">
                <template v-if="stg.status === 'finish'">已完成</template>
                <template v-else-if="stg.status === 'process'">进行中…</template>
                <template v-else>待执行</template>
              </div>
            </div>
            <div v-if="i < fakeStages.length - 1" class="pp-tut__stage-bar" />
          </div>
        </div>
        <div class="pp-tut__cta-row">
          <span class="pp-tut__form-btn pp-tut__form-btn--primary">⚡ 一键全程挖掘</span>
          <span class="pp-tut__form-btn">▶ 单步推进</span>
        </div>
      </div>

      <!-- Step 3：tool_call 卡片 -->
      <div v-else-if="s.kind === 'agent'" class="pp-tut__demo">
        <div class="pp-tut__tools">
          <div v-for="(t, i) in fakeToolCalls" :key="i" class="pp-tut__tool">
            <div class="pp-tut__tool-head">
              <span class="pp-tut__tool-icon">🔧</span>
              <code class="pp-tut__tool-name">{{ t.tool }}</code>
              <span class="pp-tut__tool-status">✓</span>
            </div>
            <div class="pp-tut__tool-args">{{ t.args }}</div>
            <div class="pp-tut__tool-result">{{ t.result }}</div>
          </div>
        </div>
      </div>

      <!-- Step 4：文件树 -->
      <div v-else-if="s.kind === 'filetree'" class="pp-tut__demo">
        <div class="pp-tut__tree">
          <ul class="pp-tut__tree-ul">
            <li v-for="r in fakeTree" :key="r.name">
              <div class="pp-tut__tree-node">{{ r.icon }} {{ r.name }}</div>
              <ul v-if="r.children" class="pp-tut__tree-ul pp-tut__tree-ul--child">
                <li v-for="c in r.children" :key="c.name">
                  <div class="pp-tut__tree-node">{{ c.icon }} {{ c.name }}</div>
                  <ul v-if="c.children" class="pp-tut__tree-ul pp-tut__tree-ul--child">
                    <li v-for="g in c.children" :key="g.name">
                      <div class="pp-tut__tree-node">{{ g.icon }} {{ g.name }}</div>
                    </li>
                  </ul>
                </li>
              </ul>
            </li>
          </ul>
        </div>
      </div>

      <!-- Step 5：对话气泡 -->
      <div v-else-if="s.kind === 'qa'" class="pp-tut__demo">
        <div class="pp-tut__chat">
          <div
            v-for="(m, i) in fakeQA"
            :key="i"
            class="pp-tut__bubble"
            :class="`pp-tut__bubble--${m.who}`"
          >
            <span class="pp-tut__bubble-who">{{ m.who === 'agent' ? '🤖 Agent' : '👤 你' }}</span>
            <span class="pp-tut__bubble-text">{{ m.text }}</span>
          </div>
        </div>
      </div>

      <!-- Step 6：导出 -->
      <div v-else-if="s.kind === 'export'" class="pp-tut__demo pp-tut__demo--export">
        <div class="pp-tut__export-card">
          <div class="pp-tut__export-icon">📄</div>
          <div class="pp-tut__export-meta">
            <div class="pp-tut__export-name">{{ exportFileName }}</div>
            <div class="pp-tut__export-sub">No.34 交底书模板 · 12 章 · 含权利要求 + 说明书 + 附图</div>
          </div>
          <span class="pp-tut__form-btn pp-tut__form-btn--primary">📥 下载 .docx</span>
        </div>
      </div>
    </section>

    <!-- 底部 CTA -->
    <footer class="pp-tut__foot">
      <button type="button" class="pp-tut__btn pp-tut__btn--ghost" @click="$emit('skip')">跳过教程</button>
      <button
        type="button"
        class="pp-tut__btn pp-tut__btn--primary"
        data-testid="tutorial-start-btn"
        @click="$emit('start')"
      >
        🚀 立即开始
      </button>
    </footer>
  </div>
</template>

<style scoped>
.pp-tut {
  padding: var(--pp-space-6) var(--pp-space-7) var(--pp-space-7);
  font-family: var(--pp-font-sans);
  color: var(--pp-color-text);
  background: var(--pp-color-surface);
}

/* ----- hero ----- */
.pp-tut__hero {
  display: flex;
  align-items: center;
  gap: var(--pp-space-5);
  padding: var(--pp-space-5) var(--pp-space-6);
  margin-bottom: var(--pp-space-6);
  border-radius: var(--pp-radius-lg);
  background: linear-gradient(135deg, #5B6CFF 0%, #8B5CF6 50%, #EC4899 100%);
  color: #fff;
}
.pp-tut__hero-text { flex: 1; }
.pp-tut__hero-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.01em;
}
.pp-tut__hero-sub {
  margin: 0;
  font-size: 14px;
  line-height: 1.65;
  opacity: 0.92;
}
.pp-tut__hero-emoji {
  font-size: 56px;
  filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.25));
}

/* ----- step ----- */
.pp-tut__step {
  margin-bottom: var(--pp-space-6);
  padding: var(--pp-space-5) var(--pp-space-5) var(--pp-space-4);
  border: 1px solid var(--pp-color-border-soft);
  border-radius: var(--pp-radius-lg);
  background: var(--pp-color-surface);
  box-shadow: var(--pp-shadow-sm);
}
.pp-tut__step-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.pp-tut__step-no {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--pp-radius-full);
  background: var(--pp-color-primary-soft);
  color: var(--pp-color-primary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.4px;
}
.pp-tut__step-title { font-size: 17px; font-weight: 700; letter-spacing: -0.005em; }
.pp-tut__step-emoji { margin-left: auto; font-size: 22px; opacity: 0.85; }
.pp-tut__step-desc {
  margin: 0 0 var(--pp-space-4);
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--pp-color-text-secondary);
}

.pp-tut__demo {
  border: 1px dashed var(--pp-color-border);
  border-radius: var(--pp-radius-md);
  padding: var(--pp-space-4) var(--pp-space-5);
  background: var(--pp-color-bg-elevated);
}

/* ----- step 1: form ----- */
.pp-tut__form-card {
  max-width: 640px;
  margin: 0 auto;
}
.pp-tut__form-row {
  display: flex;
  gap: var(--pp-space-4);
  padding: 8px 0;
  border-bottom: 1px solid var(--pp-color-border-soft);
  font-size: 13px;
}
.pp-tut__form-row:last-of-type { border-bottom: none; }
.pp-tut__form-row label {
  flex: 0 0 90px;
  color: var(--pp-color-text-tertiary);
}
.pp-tut__form-val {
  flex: 1;
  color: var(--pp-color-text);
}
.pp-tut__form-files {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.pp-tut__form-files span {
  font-size: 12px;
  background: var(--pp-color-surface);
  border: 1px solid var(--pp-color-border-soft);
  padding: 2px 8px;
  border-radius: var(--pp-radius-sm);
}
.pp-tut__chip {
  display: inline-block;
  padding: 2px 10px;
  background: var(--pp-color-surface);
  border: 1px solid var(--pp-color-border);
  border-radius: var(--pp-radius-full);
  font-size: 12px;
  color: var(--pp-color-text-secondary);
}
.pp-tut__chip--primary {
  background: var(--pp-color-primary-soft);
  color: var(--pp-color-primary);
  border-color: transparent;
}
.pp-tut__form-foot {
  margin-top: var(--pp-space-3);
  text-align: right;
}
.pp-tut__form-btn {
  display: inline-block;
  padding: 6px 16px;
  margin-left: 6px;
  border-radius: var(--pp-radius-md);
  background: var(--pp-color-surface);
  border: 1px solid var(--pp-color-border);
  font-size: 13px;
  color: var(--pp-color-text-secondary);
  cursor: default;
}
.pp-tut__form-btn--primary {
  background: linear-gradient(135deg, #5B6CFF 0%, #8B5CF6 100%);
  color: #fff;
  border-color: transparent;
  box-shadow: 0 2px 6px rgba(91, 108, 255, 0.32);
}

/* ----- step 2: timeline ----- */
.pp-tut__timeline {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 4px;
  flex-wrap: nowrap;
  padding: 4px 0;
}
.pp-tut__stage {
  position: relative;
  flex: 1 1 0;
  min-width: 0;
  text-align: center;
}
.pp-tut__stage-dot {
  position: relative;
  z-index: 2;
  width: 32px;
  height: 32px;
  margin: 0 auto 8px;
  border-radius: 50%;
  background: var(--pp-color-bg-elevated);
  border: 2px solid var(--pp-color-border);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: var(--pp-color-text-tertiary);
  font-weight: 600;
}
.pp-tut__stage--finish .pp-tut__stage-dot {
  background: var(--pp-color-primary);
  border-color: var(--pp-color-primary);
  color: #fff;
}
.pp-tut__stage--process .pp-tut__stage-dot {
  border-color: var(--pp-color-primary);
  background: var(--pp-color-surface);
  color: var(--pp-color-primary);
}
.pp-tut__pulse {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--pp-color-primary);
  animation: pp-tut-pulse 1.4s ease-in-out infinite;
}
@keyframes pp-tut-pulse {
  0%, 100% { transform: scale(0.6); opacity: 0.5; }
  50% { transform: scale(1.2); opacity: 1; }
}
.pp-tut__stage-bar {
  position: absolute;
  top: 16px;
  left: 60%;
  right: -40%;
  height: 2px;
  background: var(--pp-color-border);
  z-index: 1;
}
.pp-tut__stage--finish .pp-tut__stage-bar { background: var(--pp-color-primary); }
.pp-tut__stage-text { padding: 0 4px; }
.pp-tut__stage-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--pp-color-text);
}
.pp-tut__stage-status {
  font-size: 11px;
  color: var(--pp-color-text-tertiary);
  margin-top: 2px;
}
.pp-tut__cta-row {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-top: var(--pp-space-4);
}

/* ----- step 3: tools ----- */
.pp-tut__tools {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--pp-space-3);
}
.pp-tut__tool {
  background: var(--pp-color-surface);
  border: 1px solid var(--pp-color-border-soft);
  border-radius: var(--pp-radius-md);
  padding: 10px 12px;
  font-size: 12.5px;
}
.pp-tut__tool-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.pp-tut__tool-icon { font-size: 13px; }
.pp-tut__tool-name {
  font-family: var(--pp-font-mono, ui-monospace, monospace);
  font-size: 12px;
  background: var(--pp-color-bg-elevated);
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--pp-color-primary);
}
.pp-tut__tool-status {
  margin-left: auto;
  color: var(--pp-color-success, #16a34a);
  font-weight: 700;
}
.pp-tut__tool-args {
  font-family: var(--pp-font-mono, ui-monospace, monospace);
  font-size: 11.5px;
  color: var(--pp-color-text-tertiary);
  margin-bottom: 4px;
  word-break: break-all;
}
.pp-tut__tool-result {
  font-size: 12.5px;
  color: var(--pp-color-text-secondary);
  line-height: 1.55;
}

/* ----- step 4: tree ----- */
.pp-tut__tree {
  font-family: var(--pp-font-mono, ui-monospace, monospace);
  font-size: 13px;
  line-height: 1.75;
  color: var(--pp-color-text);
}
.pp-tut__tree-ul {
  list-style: none;
  margin: 0;
  padding: 0;
}
.pp-tut__tree-ul--child {
  margin-left: 18px;
  border-left: 1px dashed var(--pp-color-border);
  padding-left: 12px;
}
.pp-tut__tree-node {
  padding: 2px 0;
}

/* ----- step 5: chat ----- */
.pp-tut__chat {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pp-tut__bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: var(--pp-radius-md);
  font-size: 13px;
  line-height: 1.6;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.pp-tut__bubble--agent {
  align-self: flex-start;
  background: var(--pp-color-surface);
  border: 1px solid var(--pp-color-border-soft);
}
.pp-tut__bubble--user {
  align-self: flex-end;
  background: var(--pp-color-primary-soft);
  color: var(--pp-color-text);
}
.pp-tut__bubble-who {
  font-size: 11px;
  font-weight: 600;
  color: var(--pp-color-text-tertiary);
  letter-spacing: 0.3px;
}
.pp-tut__bubble--user .pp-tut__bubble-who { color: var(--pp-color-primary); }

/* ----- step 6: export ----- */
.pp-tut__demo--export { padding: var(--pp-space-4); }
.pp-tut__export-card {
  display: flex;
  align-items: center;
  gap: var(--pp-space-4);
  background: var(--pp-color-surface);
  border: 1px solid var(--pp-color-border-soft);
  border-radius: var(--pp-radius-md);
  padding: var(--pp-space-4) var(--pp-space-5);
}
.pp-tut__export-icon {
  font-size: 36px;
  width: 56px;
  height: 56px;
  border-radius: var(--pp-radius-md);
  background: var(--pp-color-primary-soft);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.pp-tut__export-meta { flex: 1; min-width: 0; }
.pp-tut__export-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--pp-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pp-tut__export-sub {
  font-size: 12px;
  color: var(--pp-color-text-tertiary);
  margin-top: 2px;
}

/* ----- foot ----- */
.pp-tut__foot {
  margin-top: var(--pp-space-6);
  display: flex;
  justify-content: flex-end;
  gap: var(--pp-space-3);
  padding-top: var(--pp-space-4);
  border-top: 1px solid var(--pp-color-border-soft);
}
.pp-tut__btn {
  height: 40px;
  padding: 0 22px;
  border-radius: var(--pp-radius-md);
  border: 1px solid var(--pp-color-border);
  background: var(--pp-color-surface);
  font-family: inherit;
  font-size: 14px;
  cursor: pointer;
  transition: var(--pp-transition);
}
.pp-tut__btn--ghost {
  color: var(--pp-color-text-secondary);
}
.pp-tut__btn--ghost:hover {
  border-color: var(--pp-color-text-tertiary);
  background: var(--pp-color-bg-elevated);
}
.pp-tut__btn--primary {
  border-color: transparent;
  background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(22, 163, 74, 0.3);
}
.pp-tut__btn--primary:hover {
  filter: brightness(1.05);
  box-shadow: 0 4px 12px rgba(22, 163, 74, 0.4);
}

/* ----- 响应式 ----- */
@media (max-width: 900px) {
  .pp-tut { padding: var(--pp-space-4); }
  .pp-tut__hero {
    flex-direction: column;
    text-align: center;
    padding: var(--pp-space-4);
  }
  .pp-tut__hero-emoji { font-size: 40px; }
  .pp-tut__tools { grid-template-columns: 1fr; }
  .pp-tut__timeline { flex-wrap: wrap; gap: 12px; }
  .pp-tut__stage { flex: 0 0 calc(50% - 6px); }
  .pp-tut__stage-bar { display: none; }
}
</style>
