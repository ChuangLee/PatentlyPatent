/**
 * v0.36: 共享 markdown 渲染工具
 * - marked v18 已默认开启 GFM (表格 / 任务列表 / 代码块)
 * - dompurify 防 XSS（chat 内容混 user + agent 输出，必须 sanitize）
 * v0.37: mermaid code block 占位 + 异步替换为 SVG
 */
import { marked } from 'marked';
import DOMPurify from 'dompurify';

marked.setOptions({
  gfm: true,
  breaks: false,   // v0.37: 关掉单行换行→<br>，避免段落间距双倍
});

// marked 自定义 renderer：把 ```mermaid ``` 代码块输出成占位 div
const renderer = new marked.Renderer();
const origCode = renderer.code.bind(renderer);
renderer.code = function (token: any): string {
  // marked v18 把 code 参数封装成 token 对象 { text, lang, escaped }
  const text = typeof token === 'string' ? token : token?.text ?? '';
  const lang = typeof token === 'string'
    ? (arguments[1] as string | undefined)
    : token?.lang ?? '';
  if ((lang || '').toLowerCase() === 'mermaid') {
    // 用 base64 编码原文，避免 sanitize 把 <-> 类语法当 HTML 改坏
    const b64 = typeof btoa === 'function'
      ? btoa(unescape(encodeURIComponent(text)))
      : Buffer.from(text, 'utf-8').toString('base64');
    return `<div class="pp-mermaid" data-mermaid="${b64}">⏳ 加载图表中…</div>`;
  }
  return origCode(token);
};

marked.use({ renderer });

// 让 DOMPurify 保留 mermaid 占位 div 的 data-mermaid 属性
DOMPurify.addHook('uponSanitizeAttribute', (_node, data) => {
  if (data.attrName === 'data-mermaid' || data.attrName === 'class') {
    data.forceKeepAttr = true;
  }
});

export function renderMarkdown(src: string): string {
  if (!src) return '';
  const raw = marked.parse(src, { async: false }) as string;
  return DOMPurify.sanitize(raw, {
    ADD_ATTR: ['target', 'rel', 'data-mermaid', 'class'],
    ADD_TAGS: ['div', 'svg'],
  });
}

// ─── mermaid 异步渲染 ───────────────────────────────────────────────────────

let _mermaidPromise: Promise<typeof import('mermaid').default> | null = null;
async function getMermaid(): Promise<typeof import('mermaid').default> {
  if (!_mermaidPromise) {
    _mermaidPromise = import('mermaid').then(mod => {
      const m = mod.default;
      m.initialize({
        startOnLoad: false,
        theme: 'default',
        securityLevel: 'loose',
        fontFamily: 'inherit',
      });
      return m;
    });
  }
  return _mermaidPromise;
}

let _mermaidIdCounter = 0;

/**
 * v0.37: 在 container 内查找所有 .pp-mermaid 占位 div，调用 mermaid 渲染替换。
 * 调用方在 v-html 后用 nextTick 调本函数即可。
 * 失败的图保留代码源码 + 错误提示，不影响其他内容。
 */
export async function renderMermaidIn(container: HTMLElement | null): Promise<void> {
  if (!container) return;
  const nodes = container.querySelectorAll<HTMLElement>('.pp-mermaid[data-mermaid]');
  if (nodes.length === 0) return;
  const mermaid = await getMermaid();
  for (const node of Array.from(nodes)) {
    // 已渲染过的跳过
    if (node.dataset.rendered === '1') continue;
    const b64 = node.dataset.mermaid || '';
    let src = '';
    try {
      src = decodeURIComponent(escape(atob(b64)));
    } catch {
      src = b64;
    }
    const id = `pp-mermaid-${++_mermaidIdCounter}`;
    try {
      const { svg } = await mermaid.render(id, src);
      node.innerHTML = svg;
      node.dataset.rendered = '1';
    } catch (err: any) {
      console.warn('[mermaid] render failed:', err?.message || err);
      // 把错误信息和源码一起展示
      const safeSrc = src.replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c] || c));
      node.innerHTML = `
        <details style="border:1px solid #f59e0b; background:#fffbeb; padding:8px 12px; border-radius:6px; color:#92400e;">
          <summary style="cursor:pointer; font-weight:600">⚠️ mermaid 渲染失败：${(err?.message || '解析错误').slice(0, 80)}</summary>
          <pre style="margin-top:8px; padding:8px; background:#fff; border-radius:4px; overflow:auto; font-size:12px">${safeSrc}</pre>
        </details>
      `;
      node.dataset.rendered = '1';
    }
  }
}
