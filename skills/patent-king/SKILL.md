---
name: patent-king
description: 检索、撰写、答辩中国专利。当用户提到"专利检索"、"prior art"、"现有技术"、"权利要求"、"专利申请"、"专利交底书"、"OA 答辩"、"审查意见"，或粘贴交底书/草稿/OA 通知书要求生成或修改时使用此 skill。
when_to_use: 处理 CN/US/PCT 专利全流程（检索/挖掘/撰写/OA答辩）。SKIP：商标、版权、域名、合同审阅。
allowed-tools: Bash(pk *) Read Write
---

# patent-king

中国专利全流程辅助 skill。本 skill 是 `pk` Python CLI 的薄包装——所有核心逻辑在 `pk/` 包内，本文件只负责"自然语言意图 → pk 子命令"路由。

## 路由表

| 用户意图 | pk 子命令 |
|---|---|
| 检索现有技术 / prior art / 找相似专利 | `pk search -i <交底.md> -o search.json` |
| 起草权要+说明书 | `pk draft -i <交底.md> -s search.json -o draft.md` |
| 体检（A22/A26/A33/R20.2） | `pk check -i draft.md -o check_report.md` |
| 改稿 + 修改超范围检查 | `pk check -i draft.md --original original.md` |
| 技术挖掘交底书 | `pk mine`（v0.2，未实现，先用 LLM 直接对话辅助） |
| OA 答辩 | `pk oa`（v0.2，未实现，先用 LLM 直接对话辅助） |

## 工作流

1. 阅读用户提供的交底书/草稿/OA。
2. 选择子命令、构造输入文件。
3. 调用 `pk <cmd> ...` 经 Bash。
4. 把输出（JSON / md）读回，按对话上下文做总结/精简，重要决策点（独权概括度、D1 重定义、A33 边界）必须列候选 + 风险标注，不替用户终判。
5. 涉及修改稿时，强制要求用户提供原申请文本，启用 `--original` 做 A33 锚定。

## 必读

- `references/lint-rules.md` — 法条体检规则速查
- `references/usage.md` — pk CLI 子命令完整参数

## 必须人审的边界

以下决策 skill 仅出"候选+风险"，不擅自定稿：
1. 独权概括度终判（强/中/弱档选哪个）
2. 最接近现有技术 D1 的重定义
3. A33 修改超范围的最终边界
4. portfolio 战略层
5. 答辩 vs 分案 vs 主动放弃
