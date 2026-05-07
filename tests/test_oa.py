"""v0.2 OA 答辩模块测试（offline mock）。"""
from __future__ import annotations

from pk.pipeline import run_oa


SAMPLE_OA = """国家知识产权局审查意见通知书
申请号：202310123456.7
审查员：王某某
审查意见：权利要求 1-3 不具备 A22.3 创造性。
对比文件 D1：CN111111111A，公开了类似的 LLM 编程辅助方法。
区别特征：本申请增加客户端缓存模型激活。该区别特征属于本领域公知常识。
"""

ORIGINAL = "原申请文本（说明书+权要）：包括客户端缓存模型激活、流式渲染、增量 diff 应用补丁。"


def test_oa_pipeline_smoke(sample_inventions):
    response = run_oa(
        oa_text=SAMPLE_OA,
        application=sample_inventions["software"],
        original=ORIGINAL,
        current_claims="1. 一种基于 LLM 的编程辅助方法...",
    )
    # Offline mock returns "" for the rhetoric step; the test just ensures the
    # pipeline glues the four sub-steps without raising.
    assert isinstance(response, str)
