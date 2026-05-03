"""Tests for warning rules (W291-W293, W391, W605)."""

from rude.rules.pycodestyle import (
    BlankLineAtEndOfFile,
    BlankLineContainsWhitespace,
    InvalidEscapeSequence,
    NoNewlineAtEndOfFile,
    TrailingWhitespace,
)
from tests.conftest import check_source


class TestTrailingWhitespace:
    """Tests for W291: trailing whitespace."""

    def test_trailing_spaces(self):
        source = "x = 1   "
        diagnostics = check_source(TrailingWhitespace, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "W291"

    def test_no_trailing_ok(self):
        source = "x = 1"
        diagnostics = check_source(TrailingWhitespace, source)
        assert len(diagnostics) == 0


class TestNoNewlineAtEndOfFile:
    """Tests for W292: no newline at end of file."""

    def test_no_newline(self):
        source = "x = 1"
        diagnostics = check_source(NoNewlineAtEndOfFile, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "W292"

    def test_with_newline_ok(self):
        source = "x = 1\n"
        diagnostics = check_source(NoNewlineAtEndOfFile, source)
        assert len(diagnostics) == 0


class TestBlankLineContainsWhitespace:
    """Tests for W293: blank line contains whitespace."""

    def test_blank_with_spaces(self):
        source = "x = 1\n   \ny = 2"
        diagnostics = check_source(BlankLineContainsWhitespace, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "W293"

    def test_truly_blank_ok(self):
        source = "x = 1\n\ny = 2"
        diagnostics = check_source(BlankLineContainsWhitespace, source)
        assert len(diagnostics) == 0


class TestBlankLineAtEndOfFile:
    """Tests for W391: blank line at end of file."""

    def test_blank_at_end(self):
        source = "x = 1\n\n"
        diagnostics = check_source(BlankLineAtEndOfFile, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "W391"

    def test_no_blank_at_end_ok(self):
        source = "x = 1\n"
        diagnostics = check_source(BlankLineAtEndOfFile, source)
        assert len(diagnostics) == 0


class TestInvalidEscapeSequence:
    """Tests for W605: invalid escape sequence."""

    def test_invalid_escape(self):
        source = r'x = "\d+"'
        diagnostics = check_source(InvalidEscapeSequence, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "W605"

    def test_raw_string_ok(self):
        source = r'x = r"\d+"'
        diagnostics = check_source(InvalidEscapeSequence, source)
        assert len(diagnostics) == 0

    def test_valid_escape_ok(self):
        source = r'x = "\n"'
        diagnostics = check_source(InvalidEscapeSequence, source)
        assert len(diagnostics) == 0

    def test_double_backslash_ok(self):
        source = r'x = "\\d+"'
        diagnostics = check_source(InvalidEscapeSequence, source)
        assert len(diagnostics) == 0
