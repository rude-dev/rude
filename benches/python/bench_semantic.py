"""Benchmark Rust semantic analysis via Python."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def test_analyze_source_large(benchmark: Any, corpus_large: list[Path]) -> None:
    from rude._rust import analyze_source

    sources = [p.read_bytes() for p in corpus_large]

    def run() -> None:
        for src in sources:
            analyze_source(source=src)

    benchmark(run)


def test_group_nodes_large(benchmark: Any, corpus_large: list[Path]) -> None:
    from rude._rust import group_nodes

    sources = [p.read_bytes() for p in corpus_large]

    def run() -> None:
        for src in sources:
            group_nodes(src, filter_types=[])

    benchmark(run)
