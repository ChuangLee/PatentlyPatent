"""patent_king CLI entry point.

Subcommands:
  pk search   关键字检索现有技术
  pk mine     交底书技术挖掘 (v0.2)
  pk draft    生成权要+说明书骨架
  pk check    法条 lint 体检
  pk oa       OA 答辩 (v0.2)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console

from pk.pipeline import run_check, run_draft, run_mine, run_oa, run_search

console = Console()


@click.group(help="patent_king — CNIPA-first 专利全流程辅助 CLI")
@click.version_option()
def main() -> None:
    pass


@main.command("search", help="关键字检索现有技术")
@click.option("--input", "-i", "input_path", type=click.Path(exists=True, path_type=Path), required=True,
              help="交底/草稿/关键词文件")
@click.option("--sources", default="cnipa,googlepatents",
              help="逗号分隔，可选 cnipa,googlepatents,epo,uspto")
@click.option("--max-results", default=20, type=int)
@click.option("--out", "-o", type=click.Path(path_type=Path), default=Path("search_result.json"))
def cmd_search(input_path: Path, sources: str, max_results: int, out: Path) -> None:
    text = input_path.read_text(encoding="utf-8")
    result = run_search(text, sources=sources.split(","), max_results=max_results)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]✓[/] 检索结果已写入 {out}")


@main.command("draft", help="生成权要+说明书骨架")
@click.option("--input", "-i", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--search-result", "-s", type=click.Path(exists=True, path_type=Path),
              help="pk search 输出的 json")
@click.option("--out", "-o", type=click.Path(path_type=Path), default=Path("draft.md"))
def cmd_draft(input_path: Path, search_result: Path | None, out: Path) -> None:
    invention = input_path.read_text(encoding="utf-8")
    prior_art = json.loads(search_result.read_text(encoding="utf-8")) if search_result else None
    draft = run_draft(invention, prior_art=prior_art)
    out.write_text(draft, encoding="utf-8")
    console.print(f"[green]✓[/] 草稿已写入 {out}")


@main.command("check", help="A22/A26/A33/R20.2 体检")
@click.option("--input", "-i", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--original", type=click.Path(exists=True, path_type=Path),
              help="原申请文本（用于 A33 修改超范围检查）")
@click.option("--out", "-o", type=click.Path(path_type=Path), default=Path("check_report.md"))
def cmd_check(input_path: Path, original: Path | None, out: Path) -> None:
    draft = input_path.read_text(encoding="utf-8")
    original_text = original.read_text(encoding="utf-8") if original else None
    report = run_check(draft, original=original_text)
    out.write_text(report, encoding="utf-8")
    console.print(f"[green]✓[/] 体检报告已写入 {out}")


@main.command("mine", help="交底书技术挖掘：问题树+效果矩阵+布局")
@click.option("--input", "-i", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--out", "-o", type=click.Path(path_type=Path), default=Path("mining.json"))
def cmd_mine(input_path: Path, out: Path) -> None:
    text = input_path.read_text(encoding="utf-8")
    result = run_mine(text)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]✓[/] 挖掘结果已写入 {out}")


@main.command("oa", help="OA 答辩：解析+三步法+A33 锚定+答辩状")
@click.option("--oa", "oa_path", type=click.Path(exists=True, path_type=Path), required=True,
              help="OA 通知书文本")
@click.option("--application", "-a", type=click.Path(exists=True, path_type=Path), required=True,
              help="本申请关键文本（说明书+权要摘要）")
@click.option("--original", type=click.Path(exists=True, path_type=Path), required=True,
              help="原申请文本（含说明书+权要，A33 锚定用）")
@click.option("--claims", "claims_path", type=click.Path(exists=True, path_type=Path), required=True,
              help="当前权利要求文本")
@click.option("--out", "-o", type=click.Path(path_type=Path), default=Path("oa_response.md"))
def cmd_oa(oa_path: Path, application: Path, original: Path, claims_path: Path, out: Path) -> None:
    response = run_oa(
        oa_text=oa_path.read_text(encoding="utf-8"),
        application=application.read_text(encoding="utf-8"),
        original=original.read_text(encoding="utf-8"),
        current_claims=claims_path.read_text(encoding="utf-8"),
    )
    out.write_text(response, encoding="utf-8")
    console.print(f"[green]✓[/] 答辩状已写入 {out}")


if __name__ == "__main__":
    main()
