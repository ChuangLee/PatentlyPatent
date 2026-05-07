"""创造性 A22.3 三步法答辩链。

心法（来自 ai_docs/research_03_cn_practice.md）：
1) 抢"最接近现有技术"D1 定义权 — 质疑领域/问题/效果是否真"最接近"
2) 重新认定"实际解决的技术问题" — 禁事后诸葛亮，基于区别特征在本申请中达到的效果重新表述
3) 打技术启示 — D1+D2 motivation？反向教导？公知常识需举证（指南 2023 新增）
"""
from __future__ import annotations

from pk.llm.client import chat

SYSTEM = """你是中国资深专利代理师。创造性答辩严格遵循 2023 修订《审查指南》三步法，并：
- 禁止"事后诸葛亮"
- 公知常识若审查员未举证，明确要求其举证
- 功能上相互支持的特征作为整体评价
"""

PROMPT = """对以下 OA 中创造性驳回（A22.3）做三步法答辩，输出三个论证链：

【步骤一：抢 D1 定义权】
质疑审查员选择的最接近现有技术（领域/问题/效果是否真最接近？是否漏了更接近的？）。

【步骤二：重定义实际解决的技术问题】
基于本申请相对 D1 的区别特征"在本申请中"所达到的技术效果，重新表述实际解决的技术问题，
拒绝审查员把区别特征塞进问题（事后诸葛亮）。

【步骤三：打技术启示】
- D1+D2(+...) 是否有 motivation 让本领域技术人员去做这种结合？
- 是否存在反向教导（teaching away）？
- 公知常识：审查员是否举证？若无，要求举证。
- 功能相互支持的特征作为整体处理。

每步给出 (a) 论点 (b) 论据（援引指南条款/判例/对比文件原文） (c) 撰写到答辩状中的话术初稿。

OA 解析：
{oa_parsed}

本申请关键信息：
{application}
"""


def three_step_response(oa_parsed: dict, application: str) -> str:
    return chat(PROMPT.format(oa_parsed=oa_parsed, application=application), system=SYSTEM)
