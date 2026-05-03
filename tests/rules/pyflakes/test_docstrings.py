"""Tests for docstring rules (F721)."""

from rude.rules.pyflakes import DoctestSyntaxError
from tests.conftest import assert_error, assert_no_errors


class TestDoctestSyntaxError:
    """Tests for F721: syntax error in doctest."""

    def test_valid_doctest_ok(self):
        assert_no_errors(
            DoctestSyntaxError,
            '''
def foo():
    """
    >>> x = 1
    >>> print(x)
    1
    """
    pass
''',
        )

    def test_doctest_with_syntax_error(self):
        assert_error(
            DoctestSyntaxError,
            '''
def foo():
    """
    >>> x = [1, 2, 3
    """
    pass
''',
            "F721",
        )

    def test_doctest_unclosed_parenthesis(self):
        assert_error(
            DoctestSyntaxError,
            '''
def foo():
    """
    >>> print(x
    """
    pass
''',
            "F721",
        )

    def test_no_doctest_ok(self):
        # Docstrings without >>> should not trigger
        assert_no_errors(
            DoctestSyntaxError,
            '''
def foo():
    """This is just a regular docstring."""
    pass
''',
        )

    def test_class_doctest_ok(self):
        assert_no_errors(
            DoctestSyntaxError,
            '''
class Foo:
    """
    >>> f = Foo()
    >>> f.bar()
    """
    pass
''',
        )

    def test_class_doctest_error(self):
        assert_error(
            DoctestSyntaxError,
            '''
class Foo:
    """
    >>> f = Foo(
    """
    pass
''',
            "F721",
        )

    def test_module_doctest_ok(self):
        assert_no_errors(
            DoctestSyntaxError,
            '''
"""
Module docstring.

>>> x = 1
>>> x + 1
2
"""
''',
        )

    def test_module_doctest_error(self):
        assert_error(
            DoctestSyntaxError,
            '''
"""
Module docstring.

>>> x = [1, 2
"""
''',
            "F721",
        )

    def test_non_docstring_ok(self):
        # Regular string assignments should not trigger
        assert_no_errors(
            DoctestSyntaxError,
            '''
x = """
>>> x = [1, 2
"""
''',
        )
