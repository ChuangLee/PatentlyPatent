"""法条 lint：A22/A26.3/A26.4/A33/R20.2/R34。"""
from __future__ import annotations

from typing import Any

from pk.validity.r20_2 import lint_r20_2
from pk.validity.a26_3 import lint_a26_3
from pk.validity.a26_4 import lint_a26_4
from pk.validity.a33 import lint_a33
from pk.validity.unity import lint_unity


def run_all_lints(draft_text: str, original: str | None = None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    findings += lint_r20_2(draft_text)
    findings += lint_a26_3(draft_text)
    findings += lint_a26_4(draft_text)
    findings += lint_unity(draft_text)
    if original:
        findings += lint_a33(draft_text, original)
    return findings
