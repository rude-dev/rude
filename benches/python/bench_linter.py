"""Benchmark end-to-end linter paths."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def test_check_file_large(
    benchmark: Any, default_linter: Any, corpus_large: list[Path]
) -> None:
    def run() -> None:
        for p in corpus_large:
            list(default_linter.check_file(p))

    benchmark(run)


def test_check_paths_streaming_large(
    benchmark: Any, default_linter: Any, corpus_large: list[Path]
) -> None:
    paths = [str(p) for p in corpus_large]

    def run() -> None:
        list(default_linter.check_paths_parallel(paths))

    benchmark(run)
