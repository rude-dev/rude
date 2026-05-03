"""Smoke tests guarding the public `rude.*` import surface.

These tests fail loudly if a name expected by plugin authors disappears from
the top-level namespace. They intentionally do NOT test behaviour -- only
that the import path exists and returns a stable type.
"""

from __future__ import annotations


def test_top_level_classes_are_importable_from_rude() -> None:
    """Plugin authors expect these names at the top level of `rude`."""
    from rude import (
        CheckOptions,
        Config,
        Diagnostic,
        Edit,
        FileContext,
        Fix,
        FixResult,
        LineRule,
        Linter,
        Location,
        Node,
        NodeLike,
        NodeType,
        Rule,
        RuleBase,
        Severity,
    )

    # Reference every import so ruff doesn't strip them -- the whole point
    # of the test is that each of these names resolves.
    _public_names = (
        CheckOptions,
        Config,
        Diagnostic,
        Edit,
        FileContext,
        Fix,
        FixResult,
        LineRule,
        Linter,
        Location,
        Node,
        NodeLike,
        NodeType,
        Rule,
        RuleBase,
        Severity,
    )
    assert all(obj is not None for obj in _public_names)

    # Minimal type sanity: these must be classes or type aliases.
    assert isinstance(Linter, type)
    assert isinstance(Rule, type)
    assert isinstance(RuleBase, type)
    assert isinstance(FixResult, type)


def test_scope_constants_re_exported_from_providers_semantic() -> None:
    """All four scope constants must be importable via the providers path."""
    from rude.providers.semantic import (
        SCOPE_CLASS,
        SCOPE_COMPREHENSION,
        SCOPE_FUNCTION,
        SCOPE_MODULE,
    )

    # They should be distinct integer constants.
    values = {SCOPE_MODULE, SCOPE_CLASS, SCOPE_FUNCTION, SCOPE_COMPREHENSION}
    assert len(values) == 4


def test_rule_base_is_the_documented_public_extension_point() -> None:
    """`rude.RuleBase` must match the class re-exported from `rude.core`."""
    from rude import RuleBase as RB_top
    from rude.core import RuleBase as RB_core

    assert RB_top is RB_core


def test_testing_helpers_are_importable_from_rude_testing() -> None:
    """`rude.testing` is the public testing home; plugin authors depend on it."""
    from rude.testing import assert_fix, assert_no_fix  # noqa: F401
