"""答辩状话术生成（终稿格式）。"""
from __future__ import annotations

from pk.llm.client import chat

SYSTEM = "你是中国资深专利代理师，撰写《意见陈述书》用书面正式语体。"

PROMPT = """请将以下三步法论证 + 修改方案合成为符合中国 CNIPA 形式的答辩状（意见陈述书）正文。
结构：
一、修改说明
二、新颖性/创造性意见陈述（按三步法）
三、其他事项
四、请求（请求驳回审查意见、维持/修改申请文件）

三步法论证：
{three_step}

修改方案：
{amendments}
"""


def render_response(three_step: str, amendments: dict) -> str:
    return chat(PROMPT.format(three_step=three_step, amendments=amendments), system=SYSTEM)
