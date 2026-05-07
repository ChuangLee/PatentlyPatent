"""Pytest fixtures: force offline LLM mode for all tests; provide sample patents."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("PK_OFFLINE_DEMO", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Force re-evaluation of OFFLINE flag in client module
    import importlib

    import pk.llm.client as c
    importlib.reload(c)
    yield


SAMPLES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_inventions() -> dict[str, str]:
    """Returns 5 minimal real-style invention disclosures by IPC category."""
    return {
        # Software / AI: based on US20210303999 (LLM serving) abstract style
        "software": (
            "一种基于大语言模型的对话式编程辅助方法。问题：现有 IDE 缺少自然语言到代码的低延迟交互。"
            "方案：在客户端缓存模型激活、按 token 流式渲染、增量 diff 应用补丁。"
            "效果：交互延迟 < 200ms，节省 60% token。"
        ),
        # Mechanical: based on CN201520xxx 电池模组结构
        "mechanical": (
            "一种锂电池模组散热结构。问题：高倍率放电时模组中心温度比边缘高 8℃。"
            "方案：在电芯之间嵌入多孔铝合金导热片，导热片内通入相变流体。"
            "效果：模组温差降至 2℃ 以内。"
        ),
        # Chemistry: 通式化合物
        "chemistry": (
            "一种式 (I) 化合物及其在治疗 EGFR 突变非小细胞肺癌中的用途。"
            "通式 R1-Aryl-R2，其中 R1 为氟、氯或甲基；R2 为氨基或羟基。"
            "效果：相对吉非替尼，对 T790M 突变型 EGFR 抑制活性提升 10 倍。"
        ),
        # Method: 工艺方法
        "method": (
            "一种钢板表面纳米涂层制备方法。问题：传统 PVD 涂层结合力不足。"
            "方案：先等离子体清洗 30s，再以 Ar/N2 = 4:1 比例溅射 TiAlN，"
            "最后 600℃ 退火 2h。效果：结合力达 80 N，硬度 32 GPa。"
        ),
        # System: 系统类
        "system": (
            "一种工业 IoT 故障预测系统。包括边缘节点（采集振动+温度）、"
            "网关（边缘推理）、云端（联邦学习）。问题：纯云端方案带宽高、隐私差。"
            "效果：带宽降 90%，预测准确率 ≥ 95%。"
        ),
    }
