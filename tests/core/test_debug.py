"""Tests for Linter debug mode."""

from collections.abc import Iterator

import pytest

from rude import Linter, Node, NodeType, Rule
from rude.core.types import Diagnostic


class BrokenRule(Rule):
    code = "BRK001"
    message = "This rule always crashes"
    node_types = {NodeType.MODULE}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        raise RuntimeError("intentional crash")
        yield  # make it a generator


def test_debug_false_yields_e001():
    """Default mode catches rule exceptions and emits E001."""
    linter = Linter(debug=False)
    linter.register(BrokenRule())
    diags = list(linter.check_source("x = 1\n"))
    assert any(d.code == "E001" for d in diags)


def test_debug_true_propagates_exception():
    """Debug mode re-raises rule exceptions."""
    linter = Linter(debug=True)
    linter.register(BrokenRule())
    with pytest.raises(RuntimeError, match="intentional crash"):
        list(linter.check_source("x = 1\n"))
