"""v0.21: SSE mine_spike 性能基线脚本（dry-run 默认开）。

用法：
    # 干运行（不实际打目标，只组装报告骨架；用于验脚本能跑）
    backend/.venv/bin/python backend/benchmark/load_test.py --dry-run

    # 真跑（仅 staging / 本地，不要在 prod）
    backend/.venv/bin/python backend/benchmark/load_test.py \
        --concurrency 5 --runs 10 --target https://blind.pub/patent

⚠️  默认禁止打 prod。--target 写到 https://blind.pub 时若未配 --i-know-its-prod 会拒。
真实压测前请确认目标是 staging / 本机 8088。

报告字段：
- p50 / p95 / avg latency_ms
- total cost USD（来自 SSE done.event 中的 total_cost_usd 字段）
- 平均 num_turns
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx


@dataclass
class RunResult:
    ok: bool
    latency_ms: float
    cost_usd: float = 0.0
    num_turns: int = 0
    error: Optional[str] = None
    stop_reason: Optional[str] = None


async def _one_run(
    client: httpx.AsyncClient,
    target_base: str,
    idea: str,
    headers: dict,
    timeout_s: float,
) -> RunResult:
    url = target_base.rstrip("/") + "/api/agent/mine_spike"
    payload = {"idea": idea, "max_turns": 6}
    t0 = time.monotonic()
    cost = 0.0
    turns = 0
    stop_reason: Optional[str] = None
    try:
        async with client.stream(
            "POST", url, json=payload, headers=headers, timeout=timeout_s,
        ) as resp:
            if resp.status_code != 200:
                body = (await resp.aread()).decode("utf-8", errors="replace")[:200]
                return RunResult(
                    ok=False, latency_ms=(time.monotonic() - t0) * 1000,
                    error=f"HTTP {resp.status_code}: {body}",
                )
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if not data_str:
                    continue
                try:
                    ev = json.loads(data_str)
                except Exception:
                    continue
                if ev.get("type") == "done":
                    cost = float(ev.get("total_cost_usd") or 0.0)
                    turns = int(ev.get("num_turns") or 0)
                    stop_reason = ev.get("stop_reason")
        return RunResult(
            ok=True, latency_ms=(time.monotonic() - t0) * 1000,
            cost_usd=cost, num_turns=turns, stop_reason=stop_reason,
        )
    except Exception as exc:  # noqa: BLE001
        return RunResult(
            ok=False, latency_ms=(time.monotonic() - t0) * 1000,
            error=f"{type(exc).__name__}: {exc}",
        )


async def _dry_run(args) -> list[RunResult]:
    """不发真请求；伪造 N 条结果，验脚本能跑出报告。"""
    out = []
    for i in range(args.runs):
        await asyncio.sleep(0.001)
        out.append(RunResult(
            ok=True,
            latency_ms=120.0 + (i % 5) * 30.0,
            cost_usd=0.0,  # mock 模式无成本
            num_turns=3,
            stop_reason="mock_complete",
        ))
    return out


async def _real_run(args) -> list[RunResult]:
    headers = {"X-User-Id": args.user_id, "Accept": "text/event-stream"}
    sem = asyncio.Semaphore(args.concurrency)
    results: list[RunResult] = []

    async with httpx.AsyncClient(http2=False) as client:
        async def _slot(i: int) -> RunResult:
            async with sem:
                return await _one_run(
                    client, args.target,
                    idea=f"{args.idea} #{i}",
                    headers=headers,
                    timeout_s=args.timeout,
                )

        coros = [_slot(i) for i in range(args.runs)]
        results = await asyncio.gather(*coros)
    return results


def _print_report(results: list[RunResult], args) -> None:
    ok = [r for r in results if r.ok]
    fail = [r for r in results if not r.ok]
    print("\n=== load_test report ===")
    print(f"target: {args.target}  concurrency: {args.concurrency}  runs: {args.runs}")
    print(f"ok: {len(ok)}  fail: {len(fail)}  dry_run: {args.dry_run}")
    if ok:
        lats = sorted(r.latency_ms for r in ok)
        p50 = statistics.median(lats)
        p95_idx = max(0, int(len(lats) * 0.95) - 1)
        p95 = lats[p95_idx]
        avg = statistics.mean(lats)
        total_cost = sum(r.cost_usd for r in ok)
        avg_turns = statistics.mean(r.num_turns for r in ok)
        print(f"latency_ms p50={p50:.1f}  p95={p95:.1f}  avg={avg:.1f}")
        print(f"total_cost_usd={total_cost:.6f}  avg_num_turns={avg_turns:.2f}")
    if fail:
        print("\nfailures (first 3):")
        for r in fail[:3]:
            print(f"  - {r.error}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="http://127.0.0.1:8088",
                    help="backend base URL")
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--idea", default="区块链 + ZK 跨链溯源压缩")
    ap.add_argument("--user-id", default="u1")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="不发真请求；伪造 N 条结果验脚本可跑")
    ap.add_argument("--i-know-its-prod", action="store_true",
                    help="目标含 blind.pub 时强制 confirm 才会真跑")
    args = ap.parse_args()

    if (
        not args.dry_run
        and "blind.pub" in args.target
        and not args.i_know_its_prod
    ):
        print(
            "ERROR: target appears to be production (blind.pub). "
            "Pass --i-know-its-prod to override or use --dry-run.",
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        results = asyncio.run(_dry_run(args))
    else:
        results = asyncio.run(_real_run(args))

    _print_report(results, args)
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
