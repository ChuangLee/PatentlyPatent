"""临时验证脚本（v0.17-C A/B 对比用）

跑 mining.py 老路径 + agent_section_demo.py 新路径，把两边输出转储到 stdout。
使用方法：python -m backend.test_agent_section
"""
from __future__ import annotations
import asyncio
import json
from pathlib import Path

from backend.app import mining
from backend.app.agent_section_demo import mine_section_via_agent


CTX = {
    "title": "基于区块链的供应链溯源轻量化方案",
    "domain": "区块链",
    "description": (
        "针对供应链溯源场景中传统区块链 TPS 低、节点资源占用高的问题，"
        "提出一种结合轻量化签名与边缘节点筛序的混合共识机制，"
        "在保持公开可验证性的同时把单节点存储降低 60% 以上。"
    ),
    "intake": {"stage": "prototype"},
}


def run_old_path() -> dict:
    sections = mining.build_sections(CTX)
    target = sections[0]  # 01-背景技术
    return {
        "name": target["name"],
        "phase": target["phase"],
        "content": target["content"],
        "external_calls": [],  # mining.py 模板生成阶段不直接调外部 API
        "lines": target["content"].count("\n") + 1,
    }


async def run_agent_path() -> dict:
    events = []
    deltas = []
    async for ev in mine_section_via_agent(
        "prior_art",
        {**CTX, "idea_text": CTX["description"]},
    ):
        events.append(ev)
        if ev.get("type") == "delta":
            deltas.append(ev["text"])
    return {
        "events": events,
        "final_markdown": "".join(deltas),
        "tool_use_count": sum(1 for e in events if e.get("type") == "tool_use"),
        "tool_result_count": sum(1 for e in events if e.get("type") == "tool_result"),
    }


def main() -> None:
    old = run_old_path()
    new = asyncio.run(run_agent_path())

    out_dir = Path("backend/storage/_compare_v017c")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "old.md").write_text(old["content"], encoding="utf-8")
    (out_dir / "agent.md").write_text(new["final_markdown"], encoding="utf-8")
    (out_dir / "agent_events.json").write_text(
        json.dumps(new["events"], ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[old] {old['name']} phase={old['phase']} lines={old['lines']}")
    print(f"[old] external_calls = {old['external_calls']}（模板阶段只埋 LLM_INJECT，0 次外部调用）")
    print(
        f"[agent] tool_use={new['tool_use_count']} "
        f"tool_result={new['tool_result_count']} "
        f"final_md_len={len(new['final_markdown'])}"
    )
    print(f"产物已写入 {out_dir}/")


if __name__ == "__main__":
    main()
