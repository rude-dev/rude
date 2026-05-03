"""Tests for rule discovery: prefix matching and filtering."""

from __future__ import annotations

import pytest

from rude.core.rule import RuleBase
from rude.core.rule_discovery import RuleDiscovery


class FakeRule:
    """Minimal stand-in for a rule class with a ``code`` attribute."""

    def __init__(self, code: str) -> None:
        self.code = code

    def __repr__(self) -> str:
        return f"FakeRule({self.code!r})"


def _make_rule_class(code: str) -> type:
    """Return a new class with a class-level ``code`` attribute."""
    return type(f"Rule_{code}", (), {"code": code})


# ------------------------------------------------------------------
# _prefix_matches (static method)
# ------------------------------------------------------------------


class TestPrefixMatches:
    """RuleDiscovery._prefix_matches(code, prefix) edge cases."""

    @staticmethod
    def test_single_letter_matches_same_category() -> None:
        assert RuleDiscovery._prefix_matches("E711", "E") is True

    @staticmethod
    def test_single_letter_rejects_different_category() -> None:
        assert RuleDiscovery._prefix_matches("E711", "F") is False

    @staticmethod
    def test_single_letter_rejects_extended_prefix() -> None:
        # "E" must not match "EX001" because 'X' is not a digit
        assert RuleDiscovery._prefix_matches("EX001", "E") is False

    @staticmethod
    def test_two_char_prefix_matches() -> None:
        assert RuleDiscovery._prefix_matches("E711", "E7") is True

    @staticmethod
    def test_exact_match() -> None:
        assert RuleDiscovery._prefix_matches("E711", "E711") is True

    @staticmethod
    def test_code_shorter_than_prefix() -> None:
        assert RuleDiscovery._prefix_matches("E7", "E711") is False


# ------------------------------------------------------------------
# _filter (instance method)
# ------------------------------------------------------------------


class TestFilter:
    """RuleDiscovery._filter with select/ignore combinations."""

    disc = RuleDiscovery()

    @pytest.fixture()
    def rule_classes(self) -> list[type[RuleBase]]:
        return [
            _make_rule_class("E711"),
            _make_rule_class("E712"),
            _make_rule_class("F401"),
            _make_rule_class("F841"),
        ]

    def _codes(self, classes: list[type[RuleBase]]) -> list[str]:
        return [c.code for c in classes]

    def test_select_e_keeps_only_e_codes(self, rule_classes: list[type[RuleBase]]) -> None:
        result = self.disc._filter(rule_classes, select=["E"], ignore=[])
        assert self._codes(result) == ["E711", "E712"]

    def test_ignore_e711_removes_it(self, rule_classes: list[type[RuleBase]]) -> None:
        result = self.disc._filter(rule_classes, select=[], ignore=["E711"])
        # select=[] means nothing is selected
        assert self._codes(result) == []

    def test_select_all_ignore_e711(self, rule_classes: list[type[RuleBase]]) -> None:
        # select=None means keep all, then ignore removes E711
        result = self.disc._filter(rule_classes, select=None, ignore=["E711"])
        assert self._codes(result) == ["E712", "F401", "F841"]

    def test_select_e_ignore_e711(self, rule_classes: list[type[RuleBase]]) -> None:
        result = self.disc._filter(rule_classes, select=["E"], ignore=["E711"])
        assert self._codes(result) == ["E712"]

    def test_none_none_returns_all(self, rule_classes: list[type[RuleBase]]) -> None:
        result = self.disc._filter(rule_classes, select=None, ignore=None)
        assert self._codes(result) == ["E711", "E712", "F401", "F841"]

    def test_select_f_keeps_only_f_codes(self, rule_classes: list[type[RuleBase]]) -> None:
        result = self.disc._filter(rule_classes, select=["F"], ignore=[])
        assert self._codes(result) == ["F401", "F841"]


class TestEntryPointDiscovery:
    """Test that load_entry_points() discovers installed plugins."""

    def test_builtin_and_entry_points_no_overlap(self) -> None:
        """Built-in rules and entry point rules should have disjoint codes."""
        rd = RuleDiscovery()
        builtin_codes = {cls.code for cls in rd.load_builtin()}
        ep_codes = {cls.code for cls in rd.load_entry_points()}
        overlap = builtin_codes & ep_codes
        assert not overlap, f"Code overlap between built-in and plugins: {overlap}"
