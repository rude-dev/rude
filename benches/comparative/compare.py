#!/usr/bin/env python3
"""Comparative benchmark: rude vs flake8 vs ruff.

Runs each tool at multiple parallelism levels and collects wall time,
CPU time, peak memory, and diagnostic counts for fair comparison.

Usage:
    uv run python benches/comparative/compare.py
    uv run python benches/comparative/compare.py --corpus large --tier tier1
    uv run python benches/comparative/compare.py --jobs 1,16
    uv run python benches/comparative/compare.py --output results.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import subprocess
import sys
import threading
import time

import psutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

CORPUS_DIR = Path(__file__).parent.parent / "corpus"
VENV_BIN = Path(__file__).parent.parent.parent / ".venv" / "bin"

TIER1_RULES = "E711,E712,E721,E722,E731,E741,E401,F631,F901,C901"
TIER2_RULES = "E,W,F,C"


@dataclass
class RunResult:
    tool: str
    tier: str
    corpus: str
    jobs: str
    wall_sec: float
    user_sec: float
    sys_sec: float
    peak_memory_mb: float
    diagnostics: int
    exit_code: int


def count_diagnostics(output: bytes) -> int:
    """Count diagnostic lines in tool output."""
    return sum(1 for line in output.splitlines() if line.strip() and b":" in line)


def run_tool(tool: str, corpus: Path, select: str, jobs: str, runs: int = 5) -> RunResult:
    """Run a linter tool and collect metrics (median of N runs)."""
    bin_path = VENV_BIN / tool
    if not bin_path.exists():
        bin_path = tool  # fall back to PATH

    if tool == "rude":
        cmd = [str(bin_path), "check", str(corpus), f"--select={select}"]
        if jobs != "auto":
            cmd.append(f"--jobs={jobs}")
    elif tool == "flake8":
        cmd = [str(bin_path), str(corpus), f"--select={select}"]
        if jobs != "auto":
            cmd.extend([f"--jobs={jobs}"])
    elif tool == "ruff":
        cmd = [str(bin_path), "check", str(corpus), f"--select={select}"]
    else:
        raise ValueError(f"Unknown tool: {tool}")

    results = []
    for _ in range(runs):
        # Snapshot cumulative child rusage BEFORE to compute delta
        before = resource.getrusage(resource.RUSAGE_CHILDREN)

        start = time.monotonic()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Poll peak RSS in a background thread while communicate() drains pipes
        peak_rss = 0
        ps = psutil.Process(proc.pid)
        stop_event = threading.Event()

        def _poll_memory() -> None:
            nonlocal peak_rss
            while not stop_event.is_set():
                try:
                    mem = ps.memory_info().rss
                    if mem > peak_rss:
                        peak_rss = mem
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break
                stop_event.wait(0.05)

        monitor = threading.Thread(target=_poll_memory, daemon=True)
        monitor.start()

        stdout, _ = proc.communicate()
        wall = time.monotonic() - start

        stop_event.set()
        monitor.join(timeout=1)

        # Delta of cumulative child rusage gives per-child CPU time
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        user_sec = after.ru_utime - before.ru_utime
        sys_sec = after.ru_stime - before.ru_stime
        peak_mb = peak_rss / (1024 * 1024) if peak_rss else 0

        results.append(RunResult(
            tool=tool,
            tier="",
            corpus="",
            jobs=jobs,
            wall_sec=wall,
            user_sec=user_sec,
            sys_sec=sys_sec,
            peak_memory_mb=peak_mb,
            diagnostics=count_diagnostics(stdout),
            exit_code=proc.returncode,
        ))

    # Return median by wall time
    results.sort(key=lambda r: r.wall_sec)
    return results[len(results) // 2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Comparative linter benchmark")
    parser.add_argument("--corpus", default="large", choices=["large", "huge"])
    parser.add_argument("--tier", default="all", choices=["tier1", "tier2", "all"])
    parser.add_argument("--jobs", default="1,auto", help="Comma-separated jobs levels")
    parser.add_argument("--runs", type=int, default=5, help="Runs per configuration")
    parser.add_argument("--output", "-o", type=str, help="Save JSON results")
    parser.add_argument("--tools", default="rude,flake8,ruff", help="Comma-separated tools")
    args = parser.parse_args()

    corpus_path = CORPUS_DIR / args.corpus
    if not corpus_path.exists():
        print(f"Corpus not found: {corpus_path}")
        print(f"Run: uv run python benches/corpus/download.py {args.corpus}")
        sys.exit(1)

    py_files = list(corpus_path.glob("**/*.py"))
    loc = sum(len(f.read_bytes().splitlines()) for f in py_files)

    tiers = {"tier1": TIER1_RULES, "tier2": TIER2_RULES}
    if args.tier != "all":
        tiers = {args.tier: tiers[args.tier]}

    jobs_levels = args.jobs.split(",")
    tools = args.tools.split(",")

    print(f"Machine: {platform.node()} ({os.cpu_count()} CPUs)")
    print(f"Corpus: {args.corpus} ({len(py_files)} files, {loc:,} LOC)")
    print(f"Tools: {', '.join(tools)}")
    print(f"Jobs: {', '.join(jobs_levels)}")
    print(f"Runs: {args.runs}")
    print()

    all_results: list[dict] = []

    for tier_name, select in tiers.items():
        print(f"=== {tier_name} ({select}) ===")
        print(f"{'Tool':<10} {'Jobs':<6} {'Wall':>8} {'User':>8} {'Mem MB':>8} {'Diags':>6} {'LOC/s':>10}")
        print("-" * 62)

        for tool in tools:
            for jobs in jobs_levels:
                if tool == "ruff" and jobs != "auto":
                    continue  # ruff doesn't support --jobs

                try:
                    r = run_tool(tool, corpus_path, select, jobs, runs=args.runs)
                except FileNotFoundError:
                    print(f"{tool:<10} {jobs:<6} {'SKIP (not installed)':>40}")
                    continue

                r.tier = tier_name
                r.corpus = args.corpus
                lps = loc / r.wall_sec if r.wall_sec > 0 else 0

                print(
                    f"{tool:<10} {jobs:<6} {r.wall_sec:>7.3f}s "
                    f"{r.user_sec:>7.3f}s {r.peak_memory_mb:>7.1f} "
                    f"{r.diagnostics:>6} {lps:>10,.0f}"
                )
                all_results.append(asdict(r))

        print()

    if args.output:
        output = {
            "machine": platform.node(),
            "cpus": os.cpu_count(),
            "corpus": args.corpus,
            "corpus_files": len(py_files),
            "corpus_loc": loc,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": all_results,
        }
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
