"""挖掘流的"先调智慧芽看看"环节 — 把 description 抽词、调 query-search-count，
得到 1) 该方向公开专利量级；2) 关键词 cloud。结果用于回填 mining.py 模板的部分注入位。
"""
from __future__ import annotations
import re
from typing import Iterable
from .zhihuiya import query_search_count, applicant_ranking, patent_trends, most_cited, ZhihuiyaError

# 中文停用词（极简）
_CN_STOP = set("的了和与或者一个一种本是在为以及或将其能可对于即不"
               "中等通过提供基于使得为本则这它如果以便由于及之上下进行实现"
               "包括具有方法系统装置一种该所述上述。、，；：（）()[]【】「」"
               "（）—-".split())

def _extract_keywords(text: str, max_n: int = 5) -> list[str]:
    """简单关键词抽取：英文按词（连字符拆分，智慧芽不接受 hyphen）+ 中文按 2-4 字 token"""
    if not text:
        return []
    # 抽英文 token；hyphen 视为分隔（智慧芽 query 对 hyphen 报 syntax error）
    en_raw = re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text)
    # 中文 2-4 字滑窗
    cn_segments = re.findall(r"[一-龥]{2,}", text)
    cn = []
    for seg in cn_segments:
        for n in (4, 3, 2):
            for i in range(0, max(0, len(seg) - n + 1)):
                w = seg[i : i + n]
                if w not in _CN_STOP:
                    cn.append(w)
    # 频率
    freq: dict[str, int] = {}
    for w in en_raw + cn:
        freq[w] = freq.get(w, 0) + 1
    common_en = {"the", "and", "for", "with", "this", "that", "has", "are"}
    items = sorted(
        [(w, c) for w, c in freq.items() if w.lower() not in common_en],
        key=lambda kv: (-kv[1], -len(kv[0])),
    )
    return [w for w, _ in items[:max_n]]


def _cql(keywords: Iterable[str]) -> str:
    """智慧芽实测：字段前缀（TACD/TI/ALL 等）一律 syntax error。
    只有 plain 关键字 + 布尔（OR/AND）能用。
    """
    parts = [k for k in keywords if k]
    return " OR ".join(parts) if parts else ""


async def quick_landscape(description: str, title: str = "") -> dict:
    """对 description 跑一次智慧芽快速洞察，返回：
    {
        "keywords": [...],
        "queries": [(kw, count), ...],
        "total_query": "...",
        "total_count": N,
        "available": True/False,
        "error": str | None,
    }
    """
    text = (title + "\n" + description).strip()
    keywords = _extract_keywords(text, max_n=5)
    out: dict = {
        "keywords": keywords,
        "queries": [],
        "total_query": "",
        "total_count": 0,
        "available": False,
        "error": None,
    }
    if not keywords:
        out["error"] = "无法从描述抽出关键词"
        return out

    try:
        # 单关键词 count（plain 关键字，不带字段前缀）
        for kw in keywords[:3]:
            try:
                cnt = await query_search_count(kw)
                out["queries"].append((kw, cnt))
            except ZhihuiyaError:
                out["queries"].append((kw, -1))
        # 综合
        total_q = _cql(keywords[:3])
        out["total_query"] = total_q
        try:
            out["total_count"] = await query_search_count(total_q)
            out["available"] = True
        except ZhihuiyaError as e:
            out["error"] = str(e)
        # 加 insights：top 申请人 + 趋势（基于综合 query）
        if out["available"] and total_q:
            try:
                out["top_applicants"] = await applicant_ranking(total_q, lang="cn", n=8)
            except Exception as e:
                out["top_applicants"] = []
                out.setdefault("warnings", []).append(f"applicants: {e}")
            try:
                out["trends"] = await patent_trends(total_q, lang="cn")
            except Exception as e:
                out["trends"] = []
                out.setdefault("warnings", []).append(f"trends: {e}")
            # v0.11-C: most_cited 套餐多数情况未开（67200203），graceful fallback
            try:
                out["most_cited"] = await most_cited(total_q, lang="cn", n=5)
            except Exception as e:
                out["most_cited"] = []
                out.setdefault("warnings", []).append(f"most_cited unavailable (套餐): {e}")
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def landscape_to_md(landscape: dict) -> str:
    """把 quick_landscape 结果格式化为 markdown 段落"""
    if not landscape.get("available"):
        err = landscape.get("error", "智慧芽未开通")
        return f"> ℹ️ 智慧芽快速洞察未跑通（{err}）；下方仍按模板提供占位\n\n"

    kw_str = ", ".join(landscape.get("keywords", [])[:5])
    rows = "\n".join(
        f"| `{kw}` | {('—' if cnt < 0 else f'{cnt:,}')} |"
        for kw, cnt in landscape.get("queries", [])
    )

    # 申请人 top 8
    apps = landscape.get("top_applicants") or []
    apps_md = ""
    if apps:
        apps_rows = "\n".join(
            f"| {i+1} | {a.get('applicant', '?')} | {a.get('count', 0):,} | {(a.get('percentage', 0)*100):.1f}% |"
            for i, a in enumerate(apps[:8])
        )
        apps_md = (
            "\n### Top 申请人（来自智慧芽 insights）\n\n"
            "| # | 申请人 | 公开数 | 占比 |\n|---|---|---|---|\n"
            f"{apps_rows}\n\n"
        )

    # 趋势：最近 5 年
    trends = landscape.get("trends") or []
    trends_md = ""
    if trends:
        recent = sorted(trends, key=lambda t: int(t.get("year", 0)))[-7:]
        rows_t = "\n".join(
            f"| {t.get('year', '?')} | {t.get('application', 0):,} | {t.get('granted', 0):,} | {(t.get('percentage', 0)*100):.0f}% |"
            for t in recent
        )
        trends_md = (
            "\n### 申请趋势（最近 7 年，来自智慧芽 insights）\n\n"
            "| 年份 | 申请数 | 授权数 | 授权率 |\n|---|---|---|---|\n"
            f"{rows_t}\n\n"
        )

    # v0.11-C: top 5 高被引专利（套餐未开时为空，仅显示提示）
    cited = landscape.get("most_cited") or []
    cited_md = ""
    if cited:
        cited_rows = "\n".join(
            f"| {i+1} | `{c.get('patent_number', '—')}` | {(c.get('title', '—') or '—')[:50]} | {c.get('cited_count', 0)} |"
            for i, c in enumerate(cited[:5])
        )
        cited_md = (
            "\n### Top 5 高被引专利（候选最近现有技术 D1）\n\n"
            "| # | 公开号 | 标题（截断） | 被引数 |\n|---|---|---|---|\n"
            f"{cited_rows}\n\n"
            "> 这 5 篇是候选 D1，建议代理人重点对照。\n\n"
        )
    else:
        warns = landscape.get("warnings", [])
        if any("most_cited" in w for w in warns):
            cited_md = "\n> ℹ️ Top 高被引文献需智慧芽套餐升级；当前已串通其他 insights。\n\n"

    return (
        "## 🔍 智慧芽快速洞察（自动生成）\n\n"
        f"**抽取的检索关键词**：{kw_str}\n\n"
        "| 检索式 | 命中量 |\n|---|---|\n"
        f"{rows}\n"
        f"| **综合 (`{landscape.get('total_query','')}`) | **{landscape.get('total_count', 0):,}** |\n"
        f"{apps_md}"
        f"{trends_md}"
        f"{cited_md}"
        "> 上述命中量为智慧芽全库搜索结果（标题+摘要+权要+说明书）。"
        "数量越大说明该方向竞争越激烈，需更细化区别特征。\n\n"
    )
