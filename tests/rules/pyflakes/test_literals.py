"""Tests for literal rules (F541, F542)."""

from rude.rules.pyflakes import (
    FStringMissingPlaceholders,
)
from tests.conftest import assert_error, assert_no_errors


class TestFStringMissingPlaceholders:
    """Tests for F541: f-string missing placeholders."""

    def test_fstring_with_placeholder_ok(self):
        assert_no_errors(
            FStringMissingPlaceholders,
            """
x = 1
s = f"value is {x}"
""",
        )

    def test_fstring_without_placeholder(self):
        assert_error(
            FStringMissingPlaceholders,
            """
s = f"hello world"
""",
            "F541",
        )

    def test_regular_string_ok(self):
        assert_no_errors(
            FStringMissingPlaceholders,
            """
s = "hello world"
""",
        )

    def test_raw_fstring_without_placeholder(self):
        assert_error(
            FStringMissingPlaceholders,
            """
s = rf"hello world"
""",
            "F541",
        )


class TestTStringMissingPlaceholders:
    """Tests for F542: t-string missing placeholders (Python 3.14+)."""

    # Note: tree-sitter may not support t-strings yet
    # These tests are placeholders for when support is added

    def test_placeholder(self):
        # t-strings are Python 3.14+, tree-sitter support may vary
        pass
