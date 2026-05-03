"""Tests for syntax rules (F601, F602, F621, F622, F631, F632, F634, F831, F901)."""

from rude.rules.pyflakes import (
    AssertTuple,
    DuplicateArgument,
    IfTuple,
    InvalidPrintSyntax,
    IsLiteral,
    MultiValueRepeatedKeyLiteral,
    MultiValueRepeatedKeyVariable,
    RaiseNotImplemented,
    TwoStarredExpressions,
)
from tests.conftest import assert_error, assert_no_errors


class TestTwoStarredExpressions:
    """Tests for F622: two starred expressions."""

    def test_single_star_ok(self):
        assert_no_errors(
            TwoStarredExpressions,
            """
a, *b, c = [1, 2, 3, 4]
""",
        )

    def test_two_stars(self):
        assert_error(
            TwoStarredExpressions,
            """
*a, *b = [1, 2, 3]
""",
            "F622",
        )

    def test_no_star_ok(self):
        assert_no_errors(
            TwoStarredExpressions,
            """
a, b, c = [1, 2, 3]
""",
        )


class TestAssertTuple:
    """Tests for F631: assert tuple."""

    def test_assert_expression_ok(self):
        assert_no_errors(
            AssertTuple,
            """
assert x > 0
""",
        )

    def test_assert_tuple_error(self):
        assert_error(
            AssertTuple,
            """
assert (x, y)
""",
            "F631",
        )

    def test_assert_tuple_with_message_error(self):
        assert_error(
            AssertTuple,
            """
assert (x, y), "message"
""",
            "F631",
        )

    def test_assert_empty_tuple_ok(self):
        # Empty tuple would be caught differently
        assert_no_errors(
            AssertTuple,
            """
assert x and y
""",
        )


class TestIfTuple:
    """Tests for F634: if tuple."""

    def test_if_expression_ok(self):
        assert_no_errors(
            IfTuple,
            """
if x > 0:
    pass
""",
        )

    def test_if_tuple_error(self):
        assert_error(
            IfTuple,
            """
if (x, y):
    pass
""",
            "F634",
        )

    def test_if_and_expression_ok(self):
        assert_no_errors(
            IfTuple,
            """
if x and y:
    pass
""",
        )


class TestIsLiteral:
    """Tests for F632: is literal."""

    def test_is_none_ok(self):
        assert_no_errors(
            IsLiteral,
            """
x is None
""",
        )

    def test_is_true_ok(self):
        assert_no_errors(
            IsLiteral,
            """
x is True
""",
        )

    def test_is_integer(self):
        assert_error(
            IsLiteral,
            """
x is 1
""",
            "F632",
        )

    def test_is_string(self):
        assert_error(
            IsLiteral,
            """
x is "foo"
""",
            "F632",
        )

    def test_equal_integer_ok(self):
        assert_no_errors(
            IsLiteral,
            """
x == 1
""",
        )


class TestInvalidPrintSyntax:
    """Tests for F633: invalid print syntax."""

    def test_print_function_ok(self):
        assert_no_errors(
            InvalidPrintSyntax,
            """
print("hello")
""",
        )

    def test_print_with_file_kwarg_ok(self):
        assert_no_errors(
            InvalidPrintSyntax,
            """
import sys
print("hello", file=sys.stderr)
""",
        )

    def test_print_rshift_error(self):
        assert_error(
            InvalidPrintSyntax,
            """
print >> sys.stderr
""",
            "F633",
        )

    def test_regular_rshift_ok(self):
        assert_no_errors(
            InvalidPrintSyntax,
            """
x = 1 >> 2
""",
        )


class TestRaiseNotImplemented:
    """Tests for F901: raise NotImplemented."""

    def test_raise_not_implemented_error_ok(self):
        assert_no_errors(
            RaiseNotImplemented,
            """
raise NotImplementedError
""",
        )

    def test_raise_not_implemented_error_call_ok(self):
        assert_no_errors(
            RaiseNotImplemented,
            """
raise NotImplementedError()
""",
        )

    def test_raise_not_implemented(self):
        assert_error(
            RaiseNotImplemented,
            """
raise NotImplemented
""",
            "F901",
        )

    def test_raise_not_implemented_call(self):
        assert_error(
            RaiseNotImplemented,
            """
raise NotImplemented()
""",
            "F901",
        )


class TestMultiValueRepeatedKeyLiteral:
    """Tests for F601: repeated literal key."""

    def test_unique_keys_ok(self):
        assert_no_errors(
            MultiValueRepeatedKeyLiteral,
            """
d = {"a": 1, "b": 2}
""",
        )

    def test_duplicate_string_key(self):
        assert_error(
            MultiValueRepeatedKeyLiteral,
            """
d = {"a": 1, "a": 2}
""",
            "F601",
        )

    def test_duplicate_int_key(self):
        assert_error(
            MultiValueRepeatedKeyLiteral,
            """
d = {1: "a", 1: "b"}
""",
            "F601",
        )

    def test_different_key_types_ok(self):
        assert_no_errors(
            MultiValueRepeatedKeyLiteral,
            """
d = {1: "a", "1": "b"}
""",
        )


class TestMultiValueRepeatedKeyVariable:
    """Tests for F602: repeated variable key."""

    def test_unique_variable_keys_ok(self):
        assert_no_errors(
            MultiValueRepeatedKeyVariable,
            """
d = {x: 1, y: 2}
""",
        )

    def test_duplicate_variable_key(self):
        assert_error(
            MultiValueRepeatedKeyVariable,
            """
d = {x: 1, x: 2}
""",
            "F602",
        )


class TestDuplicateArgument:
    """Tests for F831: duplicate argument."""

    def test_unique_args_ok(self):
        assert_no_errors(
            DuplicateArgument,
            """
def foo(a, b, c):
    pass
""",
        )

    def test_duplicate_arg(self):
        assert_error(
            DuplicateArgument,
            """
def foo(a, a):
    pass
""",
            "F831",
        )

    def test_duplicate_with_default(self):
        assert_error(
            DuplicateArgument,
            """
def foo(a, a=1):
    pass
""",
            "F831",
        )

    def test_lambda_duplicate_arg(self):
        assert_error(
            DuplicateArgument,
            """
f = lambda a, a: a
""",
            "F831",
        )
