"""LLM 注入位填充 — 把 mining.py 模板里的 <!-- [LLM_INJECT::tag::hint] --> 标记替换为实际内容

策略：
  - 有 ANTHROPIC_API_KEY → 一次性把整节 content 喂给 LLM，让它按 hint 在原位填字（保 markdown 结构）
  - 无 key（mock 模式）→ 简单 heuristic 填充（基于 ctx + tag + hint 给一句话占位）

接口：
  fill_section(content, ctx) -> str
  fill_section_async(content, ctx) -> str  （真 LLM 模式 async）
"""
from __future__ import annotations
import re
from typing import Iterable

from .config import settings

INJECT_RE = re.compile(r"<!-- \[LLM_INJECT::([^:]+)::([^\]]+)\] -->")


def _mock_replace(tag: str, hint: str, ctx: dict) -> str:
    """无 key 时的简单 heuristic 填充（基于 ctx + hint 关键字）"""
    title = ctx.get("title") or "未命名"
    domain = ctx.get("customDomain") or ctx.get("domain", "未知")
    desc = (ctx.get("description") or "").strip()

    # 按 tag 前缀分发
    t = tag.lower()
    h = hint.lower()

    if "subdomain" in t:
        return f"{domain} → {title.split('的')[-1] if '的' in title else title}（演示数据，需 AI 进一步定位）"
    if "scenarios" in t:
        return f"- 企业内部研发场景\n  - 学术 / 标准制定参考\n  - 跨部门协作产出"
    if "search_seeds" in t or "seeds" in h:
        # 简单从 description 抽词
        words = re.findall(r"[A-Za-z]{3,}", desc)[:6]
        words += [domain]
        return ", ".join(dict.fromkeys(words)) or "（需补关键词）"
    if "prior_art" in t and "title" in t:
        return f"_占位文献 {tag[-1].upper()}（由 AI 检索后回填）_"
    if "evolution" in t:
        return "_早期实现普遍存在性能/资源/可解释性瓶颈，主流方案已在多个维度做过迭代，但尚未对本案描述的具体场景给出针对性解法。_"
    if t.startswith("why"):
        if "_q" in t:
            return "（待 AI 在对话中追问）"
        if "_a" in t:
            return "（待 AI 基于检索回答）"
    if "whatif" in t:
        return "（设想替代/反序步骤的后果，留待对话补完）"
    if t.startswith("flaw_"):
        if "_pick" in t:
            return "✓"
        return "（依赖检索结果，AI 后续回填）"
    if "baseline_ask" in t:
        m = re.search(r"(相对|对比|baseline|基线)[^。，,.]{2,40}", desc)
        return m.group(0) if m else "（请告知本案对比的 baseline）"
    if "problem_oneliner" in t:
        return f"针对现有 {domain} 方案在你描述场景下的不足，本发明提供一种新方法以达到 {desc[:40]}{'…' if len(desc)>40 else ''} 的目标。"
    if "problem_core" in t:
        return f"将 {domain} 中的核心瓶颈量化提升至少一个数量级（具体数值待你补）"
    if "problem_aux" in t:
        return "（如有，请在对话中补充）"
    if "problem_out" in t:
        return "本发明不解决与本案场景无关的通用安全/合规问题；这些不在保护范围。"
    if t.startswith("kpi"):
        if "_name" in t: return "请填指标名（如吞吐 tokens/s、误报率%）"
        if "_old" in t: return "请填 baseline 数值"
        if "_new" in t: return "请填本案目标数值"
        if "_how" in t: return "请填测量方法"
    if "scheme_oneline" in t:
        return f"在 {domain} 场景下，通过 [核心手段] 实现 [量化目标]"
    if "scheme_paragraph" in t:
        return f"_本案输入为 [...]，关键步骤包括 [...]，输出为 [...]，相比现有技术的差异点在于 [...]_"
    if t.startswith("m") and ("_name" in t or "_role" in t or "_in" in t or "_out" in t or "_algo" in t):
        return "_（模块占位，等你补/AI 检索后回填）_"
    if "broad" in t:
        return "_（强档独权种子：上位最激进，5±1 个特征）_"
    if "medium" in t:
        return "_（中档独权：稳妥，7±2 个特征）_"
    if "narrow" in t:
        return "_（弱档独权：紧贴实施例，9±2 个特征）_"
    if "dep" in t and "claim" in t:
        return "_（从权梯度种子）_"
    if "advantage" in t or "improve" in t:
        return "_（待 AI 用「手段→效果」对账表实写）_"
    if "oa" in t and "step" in t:
        return "_（OA 三步法预演占位）_"
    # default
    return f"_（待 AI 填：{hint[:30]}{'…' if len(hint)>30 else ''}）_"


def fill_section_mock(content: str, ctx: dict) -> str:
    return INJECT_RE.sub(lambda m: _mock_replace(m.group(1), m.group(2), ctx), content)


async def fill_section_real(content: str, ctx: dict) -> str:
    """有 ANTHROPIC_API_KEY 时调用：一次性让 LLM 按 hint 填所有占位，保留 markdown 结构。"""
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    sys_prompt = (
        "你是企业内部专利挖掘助手。下面是一段 markdown 模板，含若干 "
        "<!-- [LLM_INJECT::tag::hint] --> 标记。请：\n"
        "1) 把每个标记原位替换为 hint 要求的内容（中文，简洁专业）；\n"
        "2) 不修改其它 markdown 结构、不添加额外章节、不删除现有标题/表头；\n"
        "3) 表格单元格内填短文本（≤30 字）；\n"
        "4) 列表项 bullet 形式；\n"
        "5) 直接返回最终 markdown，不要解释。"
    )
    proj_ctx = (
        f"项目标题：{ctx.get('title')}\n"
        f"领域：{ctx.get('customDomain') or ctx.get('domain')}\n"
        f"用户报门描述：{ctx.get('description')}\n"
        f"阶段：{(ctx.get('intake') or {}).get('stage', 'idea')}"
    )
    msg = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=sys_prompt,
        messages=[{
            "role": "user",
            "content": f"=== 项目上下文 ===\n{proj_ctx}\n\n=== 模板 ===\n{content}",
        }],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


async def fill_section(content: str, ctx: dict) -> str:
    """统一入口：自动选 real / mock"""
    if not INJECT_RE.search(content):
        return content
    if settings.use_real_llm:
        try:
            return await fill_section_real(content, ctx)
        except Exception as e:
            return fill_section_mock(content, ctx) + f"\n\n> _LLM 调用失败已 fallback mock：{type(e).__name__}_\n"
    return fill_section_mock(content, ctx)
