"""Public test helpers for rule authors.

This module exposes the standard assertion helpers used to test
rules (built-in and plugin-authored). Stable API as of v0.1.0.
"""

from __future__ import annotations

from rude.core.linter import Linter
from rude.core.rule import LineRule, Rule
from rude.core.types import Diagnostic

__all__ = [
    "assert_error",
    "assert_error_count",
    "assert_fix",
    "assert_no_errors",
    "assert_no_fix",
    "check_codes",
    "check_source",
    "fix_source",
]


def check_source(rule_class: type[Rule] | type[LineRule], source: str) -> list[Diagnostic]:
    """Check source code with a single rule and return diagnostics."""
    linter = Linter()
    linter.register(rule_class())
    return list(linter.check_source(source))


def check_codes(rule_class: type[Rule] | type[LineRule], source: str) -> list[str]:
    """Return list of diagnostic codes from checking source."""
    return [d.code for d in check_source(rule_class, source)]


def assert_no_errors(rule_class: type[Rule] | type[LineRule], source: str) -> None:
    """Assert that the rule produces no diagnostics for the source."""
    diagnostics = check_source(rule_class, source)
    assert diagnostics == [], f"Expected no errors but got: {diagnostics}"


def assert_error(
    rule_class: type[Rule] | type[LineRule], source: str, expected_code: str | None = None
) -> list[Diagnostic]:
    """Assert that the rule produces at least one error."""
    diagnostics = check_source(rule_class, source)
    assert len(diagnostics) > 0, "Expected errors but got none"
    if expected_code:
        codes = [d.code for d in diagnostics]
        assert expected_code in codes, f"Expected {expected_code} but got {codes}"
    return diagnostics


def assert_error_count(
    rule_class: type[Rule] | type[LineRule], source: str, count: int
) -> list[Diagnostic]:
    """Assert that the rule produces exactly count errors."""
    diagnostics = check_source(rule_class, source)
    assert len(diagnostics) == count, (
        f"Expected {count} errors but got {len(diagnostics)}: {diagnostics}"
    )
    return diagnostics


def fix_source(
    rule_class: type[Rule] | type[LineRule], source: str
) -> tuple[list[Diagnostic], str | None]:
    """Check and fix source with a single rule. Returns (diagnostics, fixed_source)."""
    linter = Linter()
    linter.register(rule_class())
    diagnostics, result = linter.fix_source(source)
    return diagnostics, result.source if result else None


def assert_fix(
    rule_class: type[Rule] | type[LineRule], source: str, expected: str
) -> list[Diagnostic]:
    """Assert that fixing source produces expected output."""
    diagnostics, fixed = fix_source(rule_class, source)
    assert fixed is not None, "Expected a fix but got None"
    assert fixed == expected, f"Fix mismatch:\n  got:      {fixed!r}\n  expected: {expected!r}"
    return diagnostics


def assert_no_fix(rule_class: type[Rule] | type[LineRule], source: str) -> list[Diagnostic]:
    """Assert that no fix is produced (rule has no autofix for this case)."""
    diagnostics, fixed = fix_source(rule_class, source)
    assert fixed is None, f"Expected no fix but got: {fixed!r}"
    return diagnostics
