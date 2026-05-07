"""从权梯度生成（5 档：限定核心 / 可选特征 / 数值范围 / 优选实施例 / 解释性从权）。"""
from __future__ import annotations

from pk.llm.client import chat

SYSTEM = "你是中国资深专利代理师。从权设计要做到网状引用、覆盖独权失守时的 fallback。"

PROMPT = """基于独立权利要求（候选集合），生成至少 5 项从属权利要求，按梯度组织：
1) 进一步限定核心特征
2) 增加可选特征
3) 数值范围（端点+优选值）
4) 优选实施例
5) 解释性从权（对关键术语的限缩，便于将来无效时锚回实施例）

引用关系采用网状（必要时引用前述多项），格式：
"根据权利要求 X 所述的<主题>，其特征在于，..."

独立权利要求候选：
{indep}

交底要点：
{invention}
"""


def generate_dependent_claims(indep: list[str], invention: str) -> list[str]:
    text = chat(PROMPT.format(indep="\n\n".join(indep), invention=invention), system=SYSTEM)
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(line)
    return items
