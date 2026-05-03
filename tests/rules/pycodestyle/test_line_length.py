"""Tests for line length rules (E501)."""

from rude.rules.pycodestyle import LineTooLong
from tests.conftest import check_source


class TestLineTooLong:
    """Tests for E501: line too long."""

    def test_long_line(self):
        source = "x = " + "a" * 100
        diagnostics = check_source(LineTooLong, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E501"

    def test_short_line_ok(self):
        source = "x = 1"
        diagnostics = check_source(LineTooLong, source)
        assert len(diagnostics) == 0

    def test_79_chars_ok(self):
        source = "x = " + "a" * 75  # 4 + 75 = 79
        diagnostics = check_source(LineTooLong, source)
        assert len(diagnostics) == 0

    def test_80_chars_error(self):
        source = "x = " + "a" * 76  # 4 + 76 = 80
        diagnostics = check_source(LineTooLong, source)
        assert len(diagnostics) == 1
