"""答案路由：根据用户消息内容关键词，决定追加到哪个 md 文件 / 哪个 H2 锚点。

v0.9-A 设计原则：
- 关键词命中即返回；多类命中按优先级（具体 > 一般）。
- 锚点（section_anchor）只对 _问题清单.md 生效，对应 7 / 8 / 9 三个 H2 标题。
- 其他 md 文件追加到末尾（anchor=None）。

调用：
    target = route_answer("我们做了实验，吞吐 18.4 req/s")
    -> {"file": "_问题清单.md", "anchor": "## 八、是否经过实验、模拟、使用而证明可行？"}
"""
from __future__ import annotations
from typing import Optional, TypedDict


class RouteResult(TypedDict):
    file: str
    anchor: Optional[str]
    category: str  # 调试用：命中了哪一类


# 锚点常量（与 mining.py _问题清单.md 中的 H2 一致）
ANCHOR_Q7 = "## 七、是否有别的替代方案？（扩大保护范围用）"
ANCHOR_Q8 = "## 八、是否经过实验、模拟、使用而证明可行？"
ANCHOR_Q9 = "## 九、其他有助于代理人理解的资料"


# 关键词表（按命中优先级排）
# 注意：Python 的 in 是子串匹配，对中文足够
_KEYWORDS = [
    # 第八节：实验 / 数据 / 性能（优先级最高，最具体）
    {
        "keys": ["实验", "测试", "性能", "数据", "baseline", "Baseline", "BASELINE",
                 "提升", "吞吐", "延迟", "准确率", "显存", "QPS", "qps", "req/s",
                 "tokens/s", "benchmark", "Benchmark", "复现", "可重现"],
        "file": "_问题清单.md",
        "anchor": ANCHOR_Q8,
        "category": "experiment",
    },
    # 第七节：替代方案 / 等效 / 反序
    {
        "keys": ["替代", "替代方案", "反序", "等效", "等同", "并行化", "硬件实现",
                 "软件实现", "变形例", "实施例 2", "实施例2", "替换"],
        "file": "_问题清单.md",
        "anchor": ANCHOR_Q7,
        "category": "alternatives",
    },
    # 第九节：其他资料 / 文档 / 论文 / 图
    {
        "keys": ["上传", "文档", "论文", "Figma", "figma", "PPT", "ppt",
                 "架构图", "drawio", "Excalidraw", "excalidraw", "wiki",
                 "Notebook", "notebook", "录音", "演示视频", "GIF"],
        "file": "_问题清单.md",
        "anchor": ANCHOR_Q9,
        "category": "materials",
    },
    # 关键点 / 上位概括 / 独权
    {
        "keys": ["概括", "上位", "独权", "独立权利要求", "权要", "从权",
                 "从属权利要求", "保护范围"],
        "file": "05-关键点.md",
        "anchor": None,
        "category": "claims",
    },
    # 背景技术 / 现有技术 / 文献
    {
        "keys": ["现有技术", "文献", "参考文献", "对比文件", "D1", "D2",
                 "Prior art", "prior art", "background"],
        "file": "01-背景技术.md",
        "anchor": None,
        "category": "prior_art",
    },
]


def route_answer(user_msg: str) -> Optional[RouteResult]:
    """根据用户消息识别该追加到哪个章节。返回 None 表示不命中。"""
    if not user_msg or not user_msg.strip():
        return None

    msg = user_msg

    for entry in _KEYWORDS:
        for kw in entry["keys"]:
            if kw in msg:
                return {
                    "file": entry["file"],
                    "anchor": entry["anchor"],
                    "category": entry["category"],
                }

    return None


__all__ = ["route_answer", "RouteResult", "ANCHOR_Q7", "ANCHOR_Q8", "ANCHOR_Q9"]
