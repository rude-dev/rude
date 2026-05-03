"""Test fixtures and helpers.

Thin re-export shim around rude.testing for backward compatibility
with core rule tests (tests/rules/pycodestyle, pyflakes, mccabe).
New tests and plugin tests should import directly from rude.testing.
"""

from rude.testing import (
    assert_error,
    assert_error_count,
    assert_fix,
    assert_no_errors,
    assert_no_fix,
    check_codes,
    check_source,
    fix_source,
)

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
