import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';

/** v0.29: 关闭叉号样式回归测试 — 静态检查 CSS 满足约束
 * (DOM 渲染因 a-modal teleport 到 body 无法在 happy-dom 里完整模拟)
 */

function readModal(): string {
  return readFileSync(
    path.resolve(process.cwd(), 'src/components/workbench/NewProjectModal.vue'),
    'utf8',
  );
}

describe('NewProjectModal close 按钮样式', () => {
  const css = readModal();

  it('渐变条 z-index 必须低于 close 按钮', () => {
    // 渐变条 ::before z-index: 1
    expect(css).toMatch(/\.ant-modal-content::before[\s\S]*?z-index:\s*1/);
    // close 按钮 z-index: 10
    expect(css).toMatch(/\.ant-modal-close[\s\S]*?z-index:\s*10/);
  });

  it('close 按钮高度 ≤ 渐变条高度（24px），完全收进渐变条内', () => {
    const m = css.match(/\.pp-newproj-wrap \.ant-modal-close \{[\s\S]*?\}/);
    expect(m).toBeTruthy();
    const block = m![0];
    expect(block).toMatch(/height:\s*24px\s*!important/);
    expect(block).toMatch(/top:\s*0\s*!important/);
    expect(block).toMatch(/right:\s*0\s*!important/);
  });

  it('close 按钮文字白色（与渐变条对比）', () => {
    expect(css).toMatch(/\.pp-newproj-wrap \.ant-modal-close-x[\s\S]*?color:\s*#fff\s*!important/);
  });

  it('hover 有视觉反馈（半透明白底）', () => {
    expect(css).toMatch(/\.pp-newproj-wrap \.ant-modal-close:hover[\s\S]*?background:\s*rgba\(255,\s*255,\s*255/);
  });
});
