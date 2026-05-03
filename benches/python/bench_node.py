"""Benchmark Node vs NodeProxy access patterns."""
from __future__ import annotations

from pathlib import Path
from typing import Any

SAMPLE = Path(__file__).parent.parent / "corpus" / "large" / "conf" / "global_settings.py"


def test_node_proxy_type_checks(benchmark: Any) -> None:
    if not SAMPLE.exists():
        import pytest
        pytest.skip("Corpus not found")

    from rude._rust import group_nodes
    from rude.core.node import NodeProxy
    from rude.core.parser import parse
    from rude.core.types import FileContext

    source = SAMPLE.read_bytes()
    tree = parse(source)
    ctx = FileContext(path=SAMPLE, source=source, tree=tree)
    groups = group_nodes(source, filter_types=[], tree=tree)
    entries = [
        (type_name, entry)
        for type_name, items in groups.items()
        for entry in items
    ]

    def run() -> None:
        for type_name, entry in entries:
            proxy = NodeProxy(type_name, entry, ctx)
            _ = proxy.is_call
            _ = proxy.line

    benchmark(run)


def test_node_proxy_inflate(benchmark: Any) -> None:
    if not SAMPLE.exists():
        import pytest
        pytest.skip("Corpus not found")

    from rude._rust import group_nodes
    from rude.core.node import NodeProxy
    from rude.core.parser import parse
    from rude.core.types import FileContext

    source = SAMPLE.read_bytes()
    tree = parse(source)
    ctx = FileContext(path=SAMPLE, source=source, tree=tree)
    groups = group_nodes(source, filter_types=["call"], tree=tree)
    call_entries = groups.get("call", [])

    def run() -> None:
        for entry in call_entries:
            proxy = NodeProxy("call", entry, ctx)
            _ = proxy.children

    benchmark(run)
