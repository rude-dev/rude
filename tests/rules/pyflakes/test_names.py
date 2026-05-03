"""Tests for name rules (F821, F822, F823)."""

from rude.rules.pyflakes import (
    UndefinedExport,
    UndefinedLocal,
    UndefinedName,
)
from tests.conftest import assert_error, assert_no_errors


class TestUndefinedName:
    """Tests for F821: undefined name."""

    def test_defined_name_ok(self):
        assert_no_errors(
            UndefinedName,
            """
x = 1
print(x)
""",
        )

    def test_builtin_ok(self):
        assert_no_errors(
            UndefinedName,
            """
print("hello")
len([1, 2, 3])
""",
        )

    def test_import_ok(self):
        assert_no_errors(
            UndefinedName,
            """
import os
print(os.path)
""",
        )

    def test_undefined_name(self):
        assert_error(
            UndefinedName,
            """
print(undefined_variable)
""",
            "F821",
        )

    def test_function_parameter_ok(self):
        assert_no_errors(
            UndefinedName,
            """
def foo(x):
    return x
""",
        )

    def test_for_loop_variable_ok(self):
        assert_no_errors(
            UndefinedName,
            """
for i in range(10):
    print(i)
""",
        )

    def test_comprehension_variable_ok(self):
        assert_no_errors(
            UndefinedName,
            """
[x for x in range(10)]
""",
        )

    def test_exception_variable_ok(self):
        assert_no_errors(
            UndefinedName,
            """
try:
    pass
except Exception as e:
    print(e)
""",
        )

    def test_global_statement_ok(self):
        assert_no_errors(
            UndefinedName,
            """
x = 1
def foo():
    global x
    x = 2
""",
        )

    def test_relative_import_ok(self):
        """Relative imports should not trigger F821."""
        assert_no_errors(
            UndefinedName,
            """
from .module import name
print(name)
""",
        )

    def test_aliased_import_ok(self):
        """Aliased imports should bind the alias, not the original name."""
        assert_no_errors(
            UndefinedName,
            """
from module import original as alias
print(alias)
""",
        )

    def test_keyword_argument_ok(self):
        """Keyword argument names are not uses."""
        assert_no_errors(
            UndefinedName,
            """
def func(stacklevel=1):
    pass
func(stacklevel=2)
""",
        )

    def test_lambda_parameter_ok(self):
        """Lambda parameters should be recognized."""
        assert_no_errors(
            UndefinedName,
            """
f = lambda x: x + 1
items = []
sorted(items, key=lambda a: a.name)
""",
        )

    def test_with_statement_ok(self):
        """With statement binding should work."""
        assert_no_errors(
            UndefinedName,
            """
with open('file') as f:
    print(f.read())
""",
        )

    def test_star_unpacking_ok(self):
        """Star unpacking should bind the variable."""
        assert_no_errors(
            UndefinedName,
            """
first, *rest = [1, 2, 3]
print(rest)
""",
        )

    def test_typed_parameter_ok(self):
        """Typed function parameters should be recognized."""
        assert_no_errors(
            UndefinedName,
            """
def foo(val: int):
    return val
""",
        )


class TestUndefinedExport:
    """Tests for F822: undefined export in __all__."""

    def test_defined_exports_ok(self):
        assert_no_errors(
            UndefinedExport,
            """
def foo():
    pass

__all__ = ["foo"]
""",
        )

    def test_undefined_export(self):
        assert_error(
            UndefinedExport,
            """
def foo():
    pass

__all__ = ["foo", "bar"]
""",
            "F822",
        )

    def test_empty_all_ok(self):
        assert_no_errors(
            UndefinedExport,
            """
__all__ = []
""",
        )


class TestUndefinedLocal:
    """Tests for F823: local variable used before assignment."""

    def test_assigned_before_use_ok(self):
        assert_no_errors(
            UndefinedLocal,
            """
def foo():
    x = 1
    print(x)
""",
        )

    def test_used_before_assignment(self):
        assert_error(
            UndefinedLocal,
            """
def foo():
    print(x)
    x = 1
""",
            "F823",
        )

    def test_parameter_ok(self):
        assert_no_errors(
            UndefinedLocal,
            """
def foo(x):
    print(x)
""",
        )

    def test_global_ok(self):
        assert_no_errors(
            UndefinedLocal,
            """
x = 1
def foo():
    global x
    print(x)
""",
        )

    def test_nonlocal_ok(self):
        assert_no_errors(
            UndefinedLocal,
            """
def outer():
    x = 1
    def inner():
        nonlocal x
        print(x)
""",
        )
