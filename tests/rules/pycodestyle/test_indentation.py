"""Tests for indentation rules (E1xx, W191)."""

from rude.rules.pycodestyle import (
    IndentationContainsMixedSpacesAndTabs,
    IndentationContainsTabs,
    IndentationNotMultipleOfFour,
)
from tests.conftest import check_source


class TestIndentationContainsMixedSpacesAndTabs:
    """Tests for E101: indentation contains mixed spaces and tabs."""

    def test_mixed_spaces_and_tabs(self):
        source = "def foo():\n \tx = 1"
        diagnostics = check_source(IndentationContainsMixedSpacesAndTabs, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E101"

    def test_spaces_only_ok(self):
        source = "def foo():\n    x = 1"
        diagnostics = check_source(IndentationContainsMixedSpacesAndTabs, source)
        assert len(diagnostics) == 0

    def test_tabs_only_ok(self):
        source = "def foo():\n\tx = 1"
        diagnostics = check_source(IndentationContainsMixedSpacesAndTabs, source)
        assert len(diagnostics) == 0


class TestIndentationNotMultipleOfFour:
    """Tests for E111: indentation is not a multiple of four."""

    def test_three_spaces(self):
        source = "if True:\n   x = 1"
        diagnostics = check_source(IndentationNotMultipleOfFour, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E111"

    def test_four_spaces_ok(self):
        source = "if True:\n    x = 1"
        diagnostics = check_source(IndentationNotMultipleOfFour, source)
        assert len(diagnostics) == 0

    def test_eight_spaces_ok(self):
        source = "if True:\n    if True:\n        x = 1"
        diagnostics = check_source(IndentationNotMultipleOfFour, source)
        assert len(diagnostics) == 0


class TestIndentationContainsTabs:
    """Tests for W191: indentation contains tabs."""

    def test_tab_indentation(self):
        source = "def foo():\n\tx = 1"
        diagnostics = check_source(IndentationContainsTabs, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "W191"

    def test_spaces_ok(self):
        source = "def foo():\n    x = 1"
        diagnostics = check_source(IndentationContainsTabs, source)
        assert len(diagnostics) == 0
