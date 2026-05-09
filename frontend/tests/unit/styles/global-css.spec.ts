import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';

/** v0.29: 全局 CSS 兜底规则回归测试 */

function readCss(rel: string): string {
  return readFileSync(path.resolve(process.cwd(), `src/styles/${rel}`), 'utf8');
}

describe('global.css', () => {
  it('a-modal close 按钮全局 z-index ≥ 10（防被自定义 header / 渐变条遮挡）', () => {
    const css = readCss('global.css');
    expect(css).toMatch(/\.ant-modal-close[\s\S]*?z-index:\s*10\s*!important/);
  });
});

describe('tokens.css', () => {
  it('暗色模式覆盖必需 tokens', () => {
    const css = readCss('tokens.css');
    // 关键暗色 tokens 必须存在
    const dark = css.match(/:root\[data-theme=["']dark["']\]\s*\{([\s\S]*?)\}/);
    expect(dark).toBeTruthy();
    const block = dark![1];
    expect(block).toMatch(/--pp-color-bg/);
    expect(block).toMatch(/--pp-color-surface/);
    expect(block).toMatch(/--pp-color-text/);
  });

  it('品牌色 indigo #5B6CFF 是 primary', () => {
    const css = readCss('tokens.css');
    expect(css).toMatch(/--pp-color-primary:\s*#5B6CFF/i);
  });
});
