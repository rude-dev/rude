"""Tests for blank lines rules (E3xx)."""

from rude.rules.pycodestyle import (
    BlankLinesAfterDecorator,
    ExpectedOneBlankLine,
    ExpectedTwoBlankLines,
    TooManyBlankLines,
)
from tests.conftest import check_source


class TestExpectedOneBlankLine:
    """Tests for E301: expected 1 blank line, found 0."""

    def test_no_blank_between_methods(self):
        source = """class Foo:
    def bar(self):
        pass
    def baz(self):
        pass"""
        diagnostics = check_source(ExpectedOneBlankLine, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E301"

    def test_blank_between_methods_ok(self):
        source = """class Foo:
    def bar(self):
        pass

    def baz(self):
        pass"""
        diagnostics = check_source(ExpectedOneBlankLine, source)
        assert len(diagnostics) == 0


class TestExpectedTwoBlankLines:
    """Tests for E302: expected 2 blank lines, found N."""

    def test_one_blank_line(self):
        source = """def foo():
    pass

def bar():
    pass"""
        diagnostics = check_source(ExpectedTwoBlankLines, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E302"

    def test_two_blank_lines_ok(self):
        source = """def foo():
    pass


def bar():
    pass"""
        diagnostics = check_source(ExpectedTwoBlankLines, source)
        assert len(diagnostics) == 0


class TestTooManyBlankLines:
    """Tests for E303: too many blank lines."""

    def test_three_blank_lines(self):
        source = """x = 1



y = 2"""
        diagnostics = check_source(TooManyBlankLines, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E303"

    def test_two_blank_lines_ok(self):
        source = """x = 1


y = 2"""
        diagnostics = check_source(TooManyBlankLines, source)
        assert len(diagnostics) == 0


class TestBlankLinesAfterDecorator:
    """Tests for E304: blank lines found after function decorator."""

    def test_blank_after_decorator(self):
        source = """@decorator

def foo():
    pass"""
        diagnostics = check_source(BlankLinesAfterDecorator, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E304"

    def test_no_blank_after_decorator_ok(self):
        source = """@decorator
def foo():
    pass"""
        diagnostics = check_source(BlankLinesAfterDecorator, source)
        assert len(diagnostics) == 0
