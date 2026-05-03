"""Regression tests for pathological inputs that previously crashed the analyzer."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _make_deep_source(depth: int) -> str:
    """Produce `x = [[[...1...]]]` with *depth* nested brackets."""
    return "x = " + "[" * depth + "1" + "]" * depth + "\n"


def test_deep_bracket_nesting_does_not_crash(tmp_path: Path) -> None:
    """Deeply nested brackets must not trigger a stack overflow / SIGSEGV.

    Regression test for the CRITICAL finding in the 2026-04-22 review:
    `src/analyzer.rs` previously recursed without a depth limit and exited 138
    on input with ~5000 brackets.
    """
    target = tmp_path / "deep.py"
    target.write_text(_make_deep_source(5000), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "rude", "check", str(target)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Any non-crash outcome is acceptable: a clean run, a diagnostic, or a
    # structured refusal message. What must NOT happen is a signal-termination
    # exit code. On Linux, signal-killed subprocesses return 128+N (e.g. 138
    # for SIGSEGV); on macOS, subprocess.run returns -N directly (e.g. -11).
    crash_codes = (134, 138, 139, -6, -10, -11)
    assert proc.returncode not in crash_codes, (
        f"Process died with signal-termination exit code {proc.returncode}. "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
