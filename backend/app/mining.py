"""挖掘流：基于报门 ctx 生成 7 节交底 markdown。

v0.6 升级（2026-05）：
- 借鉴 AutoPatent (arXiv:2412.09796) 的 PGTree（Patent Generation Tree）+ RRAG
  (Reference-Review-Augmented Generation) 思路，把每节拆为：
    1) PGTree 节点 overview（本节的写作目标）
    2) 子小节（subsection）骨架与"提问引导式"prompts
    3) [LLM_INJECT::xxx] 注入位 — 后续 chat.py SSE 流式让 LLM 实写
    4) Examiner 自检清单（accuracy / logic / completeness / clarity / coherence / consistency）
- 融合 v1 (pk/mining/, pk/drafting/) 的 CN 实务 prompt：
    · problem_tree.py: 5-Why + 1-What-if
    · generalize.py: 上位 / 中位 / 下位 三级概括梯度
    · effects.py: 多维技术效果矩阵
    · claims_indep.py: 三档独权（强 / 中 / 弱）+ R20.2 必要技术特征最小集
    · spec.py: A26.3 充分公开 + 实施例端点+优选值
- 仍保留 "_问题清单.md" 作为最后一节，兜住"只能用户回答"的 7/8/9 节。

接口契约（保持不变）：
    build_sections(ctx: dict) -> list[{name: str, content: str, phase: str}]
    ctx 字段：title / domain / customDomain / description / intake
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# ---------- LLM 注入位约定 ---------------------------------------------------
# chat.py 在 SSE 流式生成时，识别 [LLM_INJECT::tag::hint] 标记并替换为模型输出。
# tag = 唯一标识（如 prior_art_a），hint = 对模型的简短提示。
# 模板阶段不调用 LLM；这里只埋点。
# ----------------------------------------------------------------------------


_DOMAIN_LABEL = {
    "cryptography": "密码学",
    "infosec": "信息安全",
    "ai": "人工智能",
}

_STAGE_LABEL = {
    "idea": "只是创意",
    "prototype": "已有原型",
    "deployed": "已上线",
}


def _inject(tag: str, hint: str) -> str:
    """生成一个 LLM 注入位标记。chat.py 流式阶段识别并替换。"""
    return f"<!-- [LLM_INJECT::{tag}::{hint}] -->"


def _examiner_checklist(section_zh: str) -> str:
    """AutoPatent Examiner agent 的六维度自检清单。"""
    return f"""<details>
<summary>🔍 Examiner 自检（{section_zh}）— 点开查看 6 维度</summary>

| 维度 | 检查点 | 状态 |
|---|---|---|
| accuracy 准确性 | 与报门描述/上传资料是否一致？无臆造数字？ | ☐ |
| logic 逻辑性 | 因果链是否闭合？前后无矛盾？ | ☐ |
| completeness 完整性 | 该节要素是否齐全（领域/痛点/方案/参数/效果）？ | ☐ |
| clarity 清晰度 | 术语统一？无歧义代词？ | ☐ |
| coherence 连贯性 | 与上一节、下一节是否平滑衔接？ | ☐ |
| consistency 一致性 | 术语、参数、命名跨节是否一致？ | ☐ |

> 每一项不通过时，AI 会在对话区给出具体修改建议（Pass / Fail + advice）。
</details>"""


def build_prior_art_section_legacy(
    title: str,
    domain: str,
    desc_safe: str,
) -> dict:
    """v0.18-B 抽出：mining.py 老路径 prior_art（01-背景技术.md）章节构造。

    保留原逻辑不变，纯重构。供 build_sections 与 build_prior_art_section_smart 复用。
    """
    return {
        "name": "01-背景技术.md", "phase": "auto",
        "content": f"""# 一、背景技术

> **PGTree 节点目标**：客观铺陈技术领域全景与最相近的现有方案，**不贬损**、不下结论；
> 为第二节"缺点"和第三节"问题"做事实铺垫。

## 1.1 技术领域定位
- **本案领域**：{domain}
- **细分赛道**：{_inject("subdomain", "结合标题《" + title + "》与 description，给出 1 句话细分赛道定位（≤30 字）")}
- **典型应用场景**：{_inject("scenarios", "列举 3 个典型应用场景，bullet 形式")}

## 1.2 你报门时的描述（原文）
> {desc_safe}

## 1.3 与本发明最相近的现有技术（拟检索 3-5 篇）
> 来源：智慧芽 insights / Google Patents / arXiv 近 2 年。检索词由下方种子词扩展。

**检索种子词**：{_inject("search_seeds", "从 description 抽取 5-8 个英文检索关键词（含同义词），逗号分隔")}

| # | 标题 / 出处 | 公开年 | 核心技术手段 | 与本案差距 |
|---|---|---|---|---|
| A | {_inject("prior_art_a_title", "占位 1，等检索回填")} | — | — | — |
| B | {_inject("prior_art_b_title", "占位 2")} | — | — | — |
| C | {_inject("prior_art_c_title", "占位 3")} | — | — | — |

## 1.4 现有技术整体演进脉络（≤120 字）
{_inject("prior_art_evolution", "用 1 段话讲清楚：早期方案 → 主流方案 → 当前 SOTA 的演进，最后落到本案要改进的位置")}

---
{_examiner_checklist("背景技术")}
""",
    }


async def build_prior_art_section_smart(
    idea_text: str,
    project_id: str | None = None,
    *,
    prefer_agent: bool = True,
    title: str = "未命名项目",
    domain: str = "其他",
    desc_safe: str = "",
    timeout: float = 30.0,
) -> dict:
    """v0.18-B：prior_art 章节生成 — 优先 agent，失败 fallback legacy。

    fallback 触发条件（任一即触发）：
        1) agent 流出现 type=='error' 事件
        2) agent 整体超时（默认 30s）
        3) agent 调用抛异常（含 import 失败等）
    """
    legacy = lambda: build_prior_art_section_legacy(title, domain, desc_safe)

    if not prefer_agent:
        return legacy()

    try:
        from . import agent_section_demo  # 延迟 import 避免环依赖
    except Exception as exc:  # noqa: BLE001
        logger.info("prior_art smart: agent failed, using legacy: import-failed %s", exc)
        return legacy()

    async def _run() -> dict:
        text_parts: list[str] = []
        async for ev in agent_section_demo.mine_section_via_agent(
            "prior_art",
            {
                "idea_text": idea_text,
                "title": title,
                "domain": domain,
                "project_id": project_id,
            },
        ):
            etype = ev.get("type")
            if etype == "error":
                raise RuntimeError(f"agent error event: {ev.get('message','?')}")
            if etype == "delta":
                text_parts.append(ev.get("text", ""))
        md = "".join(text_parts).strip()
        if not md:
            raise RuntimeError("agent produced empty markdown")
        return {"name": "01-背景技术.md", "phase": "auto", "content": md}

    try:
        result = await asyncio.wait_for(_run(), timeout=timeout)
        logger.info("prior_art smart: agent ok (project_id=%s)", project_id)
        return result
    except asyncio.TimeoutError:
        logger.info("prior_art smart: agent failed, using legacy: timeout>%.0fs", timeout)
        return legacy()
    except Exception as exc:  # noqa: BLE001
        logger.info("prior_art smart: agent failed, using legacy: %s", exc)
        return legacy()


def _build_prior_art_section_dispatch(
    title: str, domain: str, desc_safe: str, project_id: str | None,
) -> dict:
    """同步入口：根据 settings.agent_prior_art 选择 smart 或 legacy。

    在已有 event loop 中（如 FastAPI async 路由）需 await，但 build_sections
    本身是同步契约；这里用 asyncio.run/get_event_loop fallback 安全调度。
    """
    from .config import settings

    if not settings.agent_prior_art:
        return build_prior_art_section_legacy(title, domain, desc_safe)

    idea_text = desc_safe if desc_safe and "未填写描述" not in desc_safe else title

    coro = build_prior_art_section_smart(
        idea_text=idea_text,
        project_id=project_id,
        prefer_agent=True,
        title=title,
        domain=domain,
        desc_safe=desc_safe,
    )

    try:
        loop = asyncio.get_event_loop()
        running = loop.is_running()
    except RuntimeError:
        loop = None
        running = False

    if running:
        # 已在事件循环里（FastAPI 路由）：用线程跑独立 loop，避免阻塞
        import concurrent.futures

        def _runner() -> dict:
            return asyncio.run(coro)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_runner).result()
    else:
        return asyncio.run(coro)


def build_sections(ctx: dict) -> list[dict]:
    title = ctx.get("title", "未命名项目")
    domain = (
        ctx.get("customDomain")
        or _DOMAIN_LABEL.get(ctx.get("domain", ""), ctx.get("domain", "其他"))
    )
    desc = (ctx.get("description") or "").strip()
    desc_safe = desc or "（用户报门时未填写描述，需在对话中补充）"
    stage = (ctx.get("intake") or {}).get("stage", "idea")
    stage_label = _STAGE_LABEL.get(stage, stage)
    project_id = ctx.get("project_id") or ctx.get("projectId")

    prior_art_section = _build_prior_art_section_dispatch(
        title=title, domain=domain, desc_safe=desc_safe, project_id=project_id,
    )

    return [
        # ===== 一、背景技术 ===========================================
        prior_art_section,

        # ===== 二、现有技术缺点 =======================================
        {
            "name": "02-现有技术缺点.md", "phase": "auto",
            "content": f"""# 二、现有技术的缺点

> **PGTree 节点目标**：用 **5-Why** 把表面缺陷一路问到根因，避免"性能差"这种空话；
> 同时用 **1-What-if** 反推规避设计的边界，为后续概括度（generalize）做准备。

## 2.1 5-Why 根因追问
> 心法（来自 v1 problem_tree.py）：连续 5 次"为什么"，把表象问题钻到机制层；
> 每一层都要给"答"，而不是"猜"。

| Why # | 问题 | 答（基于现有技术机制） |
|---|---|---|
| 1 | {_inject("why1_q", "对最相近现有技术，提出第一个 Why")} | {_inject("why1_a", "基于机制给出回答（≤40 字）")} |
| 2 | {_inject("why2_q", "顺着 Why1 答继续追问")} | {_inject("why2_a", "...")} |
| 3 | {_inject("why3_q", "...")} | {_inject("why3_a", "...")} |
| 4 | {_inject("why4_q", "...")} | {_inject("why4_a", "...")} |
| 5 | {_inject("why5_q", "根因层")} | {_inject("why5_a", "落到物理/算法/架构根因")} |

## 2.2 1-What-if 反推（规避设计边界）
> 设想：如果对手"少做"或"反着做"某一步，会怎样？这能暴露本案的"必要技术特征"。

- **What-if A**：{_inject("whatif_a", "假设对手省略某关键步骤，结果如何？")}
- **What-if B**：{_inject("whatif_b", "假设对手用反序步骤，结果如何？")}

## 2.3 多维缺点矩阵
> 心法（v1 effects.py）：缺点不止"性能"一维。八维全扫一遍，挑 3-5 个本案能解决的。

| 维度 | 现有技术现状 | 是否本案要解决 |
|---|---|---|
| 性能 / 速度 | {_inject("flaw_perf", "客观描述，给出量化数字优先")} | {_inject("flaw_perf_pick", "✓ / ✗")} |
| 资源消耗（CPU/内存/带宽） | {_inject("flaw_res", "...")} | {_inject("flaw_res_pick", "")} |
| 可靠性 / 鲁棒性 | {_inject("flaw_rel", "...")} | {_inject("flaw_rel_pick", "")} |
| 可扩展性 / 通用性 | {_inject("flaw_scale", "...")} | {_inject("flaw_scale_pick", "")} |
| 实现复杂度 / 开发成本 | {_inject("flaw_cost", "...")} | {_inject("flaw_cost_pick", "")} |
| 能耗 | {_inject("flaw_energy", "...")} | {_inject("flaw_energy_pick", "")} |
| 安全性 / 合规性 | {_inject("flaw_sec", "...")} | {_inject("flaw_sec_pick", "")} |
| 可解释性 / 可维护性 | {_inject("flaw_xai", "...")} | {_inject("flaw_xai_pick", "")} |

## 2.4 需要你确认（写实务时必填）
- 你报门里提到的"提升 X%"或"降低 X%" **相对哪个 baseline**？{_inject("baseline_ask", "若 description 已含 baseline，直接抽取；否则保留问句")}

---
{_examiner_checklist("现有技术缺点")}
""",
        },

        # ===== 三、技术问题 / 目的 ====================================
        {
            "name": "03-技术问题.md", "phase": "auto",
            "content": f"""# 三、本发明解决的技术问题或技术目的

> **PGTree 节点目标**：把第二节的"根因 + 选中的维度"翻译成一个**单一、明确、可证伪**的
> 技术问题陈述。CN 实务铁律：技术问题的颗粒度决定独权概括度的上限。

## 3.1 问题陈述（一句话版）
> 模板：「针对〈现有技术〉在〈具体场景〉下的〈根因层缺点〉，本发明提供一种〈手段类别〉，
> 以实现〈量化目标〉。」

{_inject("problem_oneliner", "套用上述模板，基于报门 description 生成 1 句话技术问题。≤80 字。")}

## 3.2 技术问题的边界（防"目的不清"导致的 A26.4 雷区）
- **核心问题**（必须解决）：{_inject("problem_core", "1 条，对应独权")}
- **附带问题**（顺带解决，从权可覆盖）：
  - {_inject("problem_aux1", "...")}
  - {_inject("problem_aux2", "...")}
- **不解决什么**（明确划界，避免审查员质疑"目的飘")：{_inject("problem_out", "...")}

## 3.3 技术目的的可量化指标（OA 第二步要用）
| 指标 | 现有技术值 | 本案目标值 | 测量方法 |
|---|---|---|---|
| {_inject("kpi1_name", "如：吞吐量 tokens/s")} | {_inject("kpi1_old", "")} | {_inject("kpi1_new", "")} | {_inject("kpi1_how", "")} |
| {_inject("kpi2_name", "")} | {_inject("kpi2_old", "")} | {_inject("kpi2_new", "")} | {_inject("kpi2_how", "")} |

> 报门原文回扣：
> > {desc_safe}

---
{_examiner_checklist("技术问题")}
""",
        },

        # ===== 四、技术方案 ==========================================
        {
            "name": "04-技术方案.md", "phase": "auto",
            "content": f"""# 四、技术方案的详细阐述

> **PGTree 节点目标**：交底书的核心。本节按 AutoPatent 的 RRAG 范式拆为
> 4 个 subsection（总览 / 模块 / 流程 / 参数），每个 subsection 独立注入 + 自检。
> 当前阶段：**{stage_label}**

---

## Subsection 1：总体方案概述（System Overview）

> 心法：先给"一句话方案"，再给"一段话方案"，最后给"一张图方案"。
> 三档颗粒度让审查员、代理人、PM 都能快速 get 到。

**一句话方案**：{_inject("scheme_oneline", "≤30 字，主谓宾齐全，含核心手段名")}

**一段话方案**（150-200 字）：
{_inject("scheme_paragraph", "覆盖：输入 / 关键步骤 / 输出 / 与现有技术的差异点")}

**架构图占位**：
```
[请上传架构图到左侧"我的资料/"。AI 会自动引用并生成附图说明。]
```

---

## Subsection 2：核心模块拆解（Module Breakdown）

> 每个模块给 4 要素：**职责 / 输入 / 输出 / 关键算法**。3-5 个模块为宜，过多说明耦合度高。

### 模块 M1：{_inject("m1_name", "命名建议：动词+名词，如「自适应温度采样器」")}
- **职责**：{_inject("m1_role", "1 句话")}
- **输入**：{_inject("m1_in", "")}
- **输出**：{_inject("m1_out", "")}
- **关键算法 / 数据结构**：{_inject("m1_algo", "若是新算法，给伪代码 5-10 行")}

### 模块 M2：{_inject("m2_name", "")}
- **职责**：{_inject("m2_role", "")}
- **输入**：{_inject("m2_in", "")}
- **输出**：{_inject("m2_out", "")}
- **关键算法 / 数据结构**：{_inject("m2_algo", "")}

### 模块 M3：{_inject("m3_name", "")}
- **职责**：{_inject("m3_role", "")}
- **输入**：{_inject("m3_in", "")}
- **输出**：{_inject("m3_out", "")}
- **关键算法 / 数据结构**：{_inject("m3_algo", "")}

---

## Subsection 3：执行流程（Workflow / 时序）

> 用「编号 + 输入→处理→输出」的形式，**每步可独立成为方法权要的一个 step**。

1. **Step 1**：{_inject("step1", "动词开头，含输入与输出")}
2. **Step 2**：{_inject("step2", "")}
3. **Step 3**：{_inject("step3", "")}
4. **Step 4**：{_inject("step4", "")}
5. **Step 5（可选）**：{_inject("step5", "若不必要可写 N/A")}

**异常 / 兜底分支**：{_inject("workflow_fallback", "列 1-2 个分支，便于从权布局")}

---

## Subsection 4：关键参数与阈值（Parameter Table）

> 心法（v1 spec.py）：参数必须给**端点 + 优选值**，否则 A26.3 充分公开扛不住。

| 参数 | 取值范围 | 优选值 | 物理含义 / 选取依据 |
|---|---|---|---|
| {_inject("p1_name", "")} | {_inject("p1_range", "")} | {_inject("p1_pref", "")} | {_inject("p1_why", "")} |
| {_inject("p2_name", "")} | {_inject("p2_range", "")} | {_inject("p2_pref", "")} | {_inject("p2_why", "")} |
| {_inject("p3_name", "")} | {_inject("p3_range", "")} | {_inject("p3_pref", "")} | {_inject("p3_why", "")} |

## 附图清单（如有）
{_inject("figures_list", "若用户已上传图，列「图1：xxx；图2：xxx」；否则列出建议补充的 3 张图")}

---
{_examiner_checklist("技术方案")}
""",
        },

        # ===== 五、关键点与欲保护点（含三档独权种子）==================
        {
            "name": "05-关键点.md", "phase": "auto",
            "content": f"""# 五、本发明的关键点和欲保护点

> **PGTree 节点目标**：把第四节的方案蒸馏成"创新点 → 上位/中位/下位"梯度，
> 直接喂给后续 claims_indep / claims_dep 阶段。
> 心法来自 v1 generalize.py + claims_indep.py。

## 5.1 创新点清单
> 一个独权对应一个创新点；一个创新点对应一个"必要技术特征最小集"（R20.2）。

### 创新点 #1（核心）
- **一句话**：{_inject("ip1_oneline", "动词开头，含手段+效果")}
- **必要技术特征最小集**：{_inject("ip1_min_features", "5±1 条 bullet，每条都不可省")}
- **支撑实施例**：{_inject("ip1_example", "对应第四节哪个模块/步骤")}

### 创新点 #2（辅助）
- **一句话**：{_inject("ip2_oneline", "")}
- **必要技术特征最小集**：{_inject("ip2_min_features", "")}
- **支撑实施例**：{_inject("ip2_example", "")}

### 创新点 #3（防御 / 外围）
- **一句话**：{_inject("ip3_oneline", "")}
- **必要技术特征最小集**：{_inject("ip3_min_features", "")}

## 5.2 三档概括度（独权种子，供撰写阶段挑选）
> 来自 v1 claims_indep.py 的"3 档心法"：能撑多大撑多大，但边界是「现有技术 + 审查员合理质疑」。

### 🟢 强档（aggressive）— 上位最激进
- **概括描述**：{_inject("indep_strong", "技术特征 5±1，上位词激进")}
- **风险标注**：{_inject("indep_strong_risk", "high / mid / low + 一句话理由（潜在 X 全/Y 缺新颖性 风险）")}

### 🟡 中档（balanced）— 稳妥
- **概括描述**：{_inject("indep_mid", "技术特征 7±2，中位")}
- **风险标注**：{_inject("indep_mid_risk", "通常 mid")}

### 🔴 弱档（conservative）— 紧贴实施例
- **概括描述**：{_inject("indep_weak", "技术特征 9±2，下位")}
- **风险标注**：{_inject("indep_weak_risk", "通常 low，但保护范围窄")}

## 5.3 从权梯度种子（5 类）
> 来自 v1 claims_dep.py：网状引用 + 失守 fallback。

1. **进一步限定核心**：{_inject("dep_refine_core", "")}
2. **可选附加特征**：{_inject("dep_optional", "")}
3. **数值范围**（端点 + 优选值）：{_inject("dep_numeric", "对应第四节参数表")}
4. **优选实施例**：{_inject("dep_preferred", "")}
5. **解释性从权**（关键术语限缩）：{_inject("dep_explain", "便于将来无效时锚回实施例")}

---
{_examiner_checklist("关键点与欲保护点")}
""",
        },

        # ===== 六、相比现有技术的优点（多维效果矩阵）==================
        {
            "name": "06-优点.md", "phase": "auto",
            "content": f"""# 六、相比现有技术的优点

> **PGTree 节点目标**：把第四节技术方案 × 第二节缺点矩阵，**对账式**生成多维效果。
> 心法（v1 effects.py）：一手段 → 多效果，OA 三步法第二步全靠它。

## 6.1 手段 → 效果对账表
> 每行：本案的某个"手段"如何带来某个"效果"，给量化数字。

| 手段（来自第四节） | 维度 | 效果（含数字） | 测量方法 / 实验环境 |
|---|---|---|---|
| {_inject("ben1_means", "")} | 性能 | {_inject("ben1_perf", "如：H100 上吞吐 2.3×")} | {_inject("ben1_setup", "")} |
| {_inject("ben2_means", "")} | 资源 | {_inject("ben2_res", "如：显存 -38%")} | {_inject("ben2_setup", "")} |
| {_inject("ben3_means", "")} | 可靠性 | {_inject("ben3_rel", "如：故障率 ↓ 1 数量级")} | {_inject("ben3_setup", "")} |
| {_inject("ben4_means", "")} | 可扩展性 | {_inject("ben4_scale", "")} | {_inject("ben4_setup", "")} |
| {_inject("ben5_means", "")} | 成本 / 复杂度 | {_inject("ben5_cost", "")} | {_inject("ben5_setup", "")} |

## 6.2 创造性叙事（OA 三步法预演）
> 当审查员引证 D1+D2 拼合时，下面这段话直接复用到答辩里。

**Step 1（确定最接近现有技术）**：{_inject("step1_closest", "选第一节哪一篇做 D1，给理由")}

**Step 2（确定区别特征 + 实际解决的技术问题）**：{_inject("step2_diff", "区别特征 = 本案有 - D1 没有；实际解决问题 = 区别特征带来的效果")}

**Step 3（判断显而易见性）**：{_inject("step3_nonobvious", "证明 D1 + 公知常识 / D2 不能轻易组合得到本案；可援引「教导远离」「意想不到的技术效果」")}

## 6.3 数字硬度自查
> ⚠️ 数字越具体越有利于创造性论证。"在 H100 上吞吐 2.3×" 比 "性能更高" 强一个量级。

- 是否每个效果都有量化？{_inject("num_check", "Y/N + 缺哪几条")}
- 是否给出测量环境（硬件 / 数据集 / baseline）？{_inject("setup_check", "Y/N")}

---
{_examiner_checklist("相比现有技术的优点")}
""",
        },

        # ===== 七 / 八 / 九：用户必答（不能 AI 代笔）====================
        {
            "name": "_问题清单.md", "phase": "ask",
            "content": f"""# ❓ 还需要你帮忙的问题清单

AI 已自动填好（含 LLM 注入位）了 1、2、3、4、5、6 这几节的初稿。
下面这 3 节**必须由你回答**——它们是事实/数据/材料，AI 不能替你编。

---

## 七、是否有别的替代方案？（扩大保护范围用）
> CN 实务：替代方案是从权与"等同侵权"判定的弹药库。哪怕只想到 1 条也写下来。

请回答：
- 同样的发明目的，能否把 **X 替换成 Y**？例如把哈希算法 SHA-256 换成 BLAKE3。
- 能否把**步骤反序**或**并行化**实现同样效果？
- 能否把**软件实现换成硬件实现**（或反过来）？
- 能否在**不同应用场景**复用本方案？（医疗 / 金融 / 边缘 / 云）

> 💬 回答任意条都可以，AI 会帮你扩成"实施例 2 / 3 / 变形例"。

---

## 八、是否经过实验、模拟、使用而证明可行？
> CN 实务：A26.3 充分公开 + 创造性论证都吃这一节。

请回答：
- **实验数据 / 性能基准**：具体数字是多少？（吞吐 / 延迟 / 准确率 / 显存…）
- **测量环境**：硬件 / 数据集 / 框架版本 / 随机种子
- **对比 baseline**：是哪个版本？为什么选它？
- **可重现性**：代码 / 数据是否可分享给代理人参考（仅做内部理解，不公开）

> 📊 如果你有实验日志/CSV，直接传到左侧"我的资料/"，AI 会抽数字进 06-优点.md。

---

## 九、其他有助于代理人理解的资料
> 越多越好。下面任意一种都欢迎：

- 📄 设计文档 / 架构图（Figma / Excalidraw / drawio）
- 📃 论文 / 技术报告 / 内部 wiki
- 💻 代码片段（核心算法函数即可，不需要全仓）
- 📊 实验数据 (CSV / Notebook)
- 🎬 演示视频 / GIF
- 🗣️ 录音口述（AI 可以帮你转写整理）

---

## 报门信息回顾（方便你对照回答）

- **项目标题**：{title}
- **技术领域**：{domain}
- **当前阶段**：{stage_label}
- **报门描述**：
  > {desc_safe}

---

💬 你可以**直接在下方聊天框**回答任意一项，或上传文件后告诉我"看这个"。我会更新对应章节，
   并在第 1-6 节的 `[LLM_INJECT::xxx]` 注入位逐步替换为正式正文。

🔍 当 1-6 节所有注入位都被替换后，AI 会跑一遍 **Examiner 6 维度自检**（accuracy / logic /
   completeness / clarity / coherence / consistency），不通过的会回到对话区让你确认。
""",
        },
    ]
