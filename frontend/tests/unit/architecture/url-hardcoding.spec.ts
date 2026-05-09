import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';

/**
 * v0.34 架构防回归测试 — URL 硬编码扫描
 *
 * 历史 bug：v0.34 subagent 用 `fetch('/api/agent/runs/...')` 直接写死路径，
 * 在 prod (nginx /patent/api) 全部 404。修复后规则：
 *   - 一切后端调用必须走 apiClient (axios) 或 _apiBase() 拼前缀
 *   - 不允许任何源文件出现裸 fetch('/api/...) 或 consumeSSE('/api/...)
 *
 * 这个测试**静态扫描** src/ 下所有 .ts/.vue 文件，发现裸字符串就 fail。
 */

const SRC = path.resolve(process.cwd(), 'src');

function walk(dir: string, out: string[] = []): string[] {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e === 'dist' || e.startsWith('.')) continue;
    const p = path.join(dir, e);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(ts|vue)$/.test(e)) out.push(p);
  }
  return out;
}

const files = walk(SRC);

/** 找出 patterns，返回违规位置 [{file, line, snippet}] */
function findViolations(re: RegExp): Array<{ file: string; line: number; snippet: string }> {
  const hits: Array<{ file: string; line: number; snippet: string }> = [];
  for (const f of files) {
    // 跳过 mock 目录（MSW handler 故意写完整路径）+ 测试文件 + types
    if (f.includes('/mock/') || f.includes('/tests/') || f.endsWith('.spec.ts')) continue;
    const text = readFileSync(f, 'utf8');
    text.split('\n').forEach((line, i) => {
      if (line.match(re)) {
        hits.push({
          file: path.relative(SRC, f),
          line: i + 1,
          snippet: line.trim().slice(0, 120),
        });
      }
    });
  }
  return hits;
}

describe('URL 硬编码防回归（v0.34 fix）', () => {
  it('不允许 fetch(\'/api/...\')  必须走 apiClient 或 _apiBase()', () => {
    const violations = findViolations(/\bfetch\s*\(\s*['"`]\/api\//);
    expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
  });

  it('不允许 consumeSSE(\'/api/...\')  必须用 ${_apiBase()}/...', () => {
    // 允许模板字符串 `${_apiBase()}/api/xxx`，禁裸 `/api/xxx`
    const violations = findViolations(/consumeSSE\s*\(\s*['"`]\/api\//);
    expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
  });

  it('不允许 apiClient.{get,post,put,delete,patch}(\'/api/...\')  baseURL 已含 /api', () => {
    const violations = findViolations(/apiClient\.(get|post|put|delete|patch)\s*<[^>]*>?\s*\(\s*['"`]\/api\//);
    expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
  });

  it('不允许直接硬编码 /patent/api/  必须由 baseURL 决定', () => {
    // 允许 backendDownloadUrl 这种用户已知动态拼接（路径里有 ${pid}）
    // 但纯字符串 '/patent/api/...' 是 bug
    const violations = findViolations(/['"`]\/patent\/api\//);
    // FilePreviewer 和 FileTree 里有 backendDownloadUrl 的 /patent/api 字面量，
    // 但那是后端 url 字段映射前端可访问 URL 的工具，加白名单
    const real = violations.filter(v => !v.file.includes('FilePreviewer') && !v.file.includes('FileTree') && !v.file.includes('api/files'));
    expect(real, JSON.stringify(real, null, 2)).toEqual([]);
  });
});
