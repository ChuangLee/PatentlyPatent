export const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

export const rand = (min: number, max: number) =>
  Math.floor(Math.random() * (max - min + 1)) + min;

/** 把字符串按 grapheme（中文按字符）切成 size 大小的片，用于伪流式 chunk */
export function splitByGrapheme(text: string, size: number): string[] {
  const chars = Array.from(text); // Array.from 处理 unicode 比 split('') 更安全
  const out: string[] = [];
  for (let i = 0; i < chars.length; i += size) {
    out.push(chars.slice(i, i + size).join(''));
  }
  return out;
}
