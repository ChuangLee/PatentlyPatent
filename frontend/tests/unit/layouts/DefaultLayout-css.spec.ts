import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';

/**
 * v0.34.2 防回归：sidebar 项目卡片 ⋯ 按钮覆盖标题 bug
 *
 * 历史：v0.14 加 hover ⋯ 按钮 absolute right:6 但 .pp-proj-item padding-right=10
 *       2 行 webkit-line-clamp 标题会延伸到按钮下方与之重叠。
 * 修复：padding-right ≥ 28（按钮宽度 20 + 边距 6+2 ≈ 28）
 */

function readFile(): string {
  return readFileSync(
    path.resolve(process.cwd(), 'src/layouts/DefaultLayout.vue'),
    'utf8',
  );
}

describe('DefaultLayout sidebar 项目卡片样式', () => {
  const css = readFile();

  it('.pp-proj-item padding-right ≥ 28px 给 ⋯ 按钮预留位置', () => {
    const m = css.match(/\.pp-proj-item\s*\{([\s\S]*?)\}/);
    expect(m).toBeTruthy();
    const block = m![1];
    // 提取 padding 值；支持 1/2/4 值缩写
    const padMatch = block.match(/padding:\s*([^;]+);/);
    expect(padMatch).toBeTruthy();
    const parts = padMatch![1].trim().split(/\s+/).map(s => parseInt(s, 10));
    let right: number;
    if (parts.length === 1) right = parts[0];
    else if (parts.length === 2) right = parts[1];
    else if (parts.length === 3) right = parts[1];
    else right = parts[1]; // 4-value top right bottom left
    expect(right, `padding-right=${right}px 不足 28px，⋯ 按钮会覆盖标题`).toBeGreaterThanOrEqual(28);
  });

  it('.pp-proj-actions 必须 absolute + 给定 right 偏移', () => {
    const m = css.match(/\.pp-proj-actions\s*\{([\s\S]*?)\}/);
    expect(m).toBeTruthy();
    expect(m![1]).toMatch(/position:\s*absolute/);
    expect(m![1]).toMatch(/right:\s*\d+px/);
  });

  it('.pp-proj-actions hover 显示（透明度切换）', () => {
    expect(css).toMatch(/\.pp-proj-actions[\s\S]*?opacity:\s*0/);
    expect(css).toMatch(/\.pp-proj-item:hover\s+\.pp-proj-actions[\s\S]*?opacity:\s*1/);
  });
});
