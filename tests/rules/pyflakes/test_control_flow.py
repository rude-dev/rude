"""Tests for control flow rules (F701, F702, F704, F706, F707)."""

from rude.rules.pyflakes import (
    BreakOutsideLoop,
    ContinueOutsideLoop,
    DefaultExceptNotLast,
    ReturnOutsideFunction,
    YieldOutsideFunction,
)
from tests.conftest import assert_error, assert_no_errors


class TestReturnOutsideFunction:
    """Tests for F706: return outside function."""

    def test_return_in_function_ok(self):
        assert_no_errors(
            ReturnOutsideFunction,
            """
def foo():
    return 1
""",
        )

    def test_return_in_async_function_ok(self):
        assert_no_errors(
            ReturnOutsideFunction,
            """
async def foo():
    return 1
""",
        )

    def test_return_in_lambda_ok(self):
        # Lambda returns are implicit, but should not trigger
        assert_no_errors(
            ReturnOutsideFunction,
            """
f = lambda: 1
""",
        )

    def test_return_at_module_level(self):
        assert_error(ReturnOutsideFunction, "return 1", "F706")

    def test_return_in_class_body(self):
        assert_error(
            ReturnOutsideFunction,
            """
class Foo:
    return 1
""",
            "F706",
        )


class TestYieldOutsideFunction:
    """Tests for F704: yield outside function."""

    def test_yield_in_function_ok(self):
        assert_no_errors(
            YieldOutsideFunction,
            """
def gen():
    yield 1
""",
        )

    def test_yield_from_in_function_ok(self):
        assert_no_errors(
            YieldOutsideFunction,
            """
def gen():
    yield from [1, 2, 3]
""",
        )

    def test_yield_at_module_level(self):
        assert_error(YieldOutsideFunction, "yield 1", "F704")

    def test_yield_in_class_body(self):
        assert_error(
            YieldOutsideFunction,
            """
class Foo:
    yield 1
""",
            "F704",
        )


class TestContinueOutsideLoop:
    """Tests for F702: continue outside loop."""

    def test_continue_in_for_ok(self):
        assert_no_errors(
            ContinueOutsideLoop,
            """
for i in range(10):
    continue
""",
        )

    def test_continue_in_while_ok(self):
        assert_no_errors(
            ContinueOutsideLoop,
            """
while True:
    continue
""",
        )

    def test_continue_in_nested_loop_ok(self):
        assert_no_errors(
            ContinueOutsideLoop,
            """
for i in range(10):
    for j in range(10):
        continue
""",
        )

    def test_continue_at_module_level(self):
        assert_error(ContinueOutsideLoop, "continue", "F702")

    def test_continue_in_function_without_loop(self):
        assert_error(
            ContinueOutsideLoop,
            """
def foo():
    continue
""",
            "F702",
        )


class TestBreakOutsideLoop:
    """Tests for F701: break outside loop."""

    def test_break_in_for_ok(self):
        assert_no_errors(
            BreakOutsideLoop,
            """
for i in range(10):
    break
""",
        )

    def test_break_in_while_ok(self):
        assert_no_errors(
            BreakOutsideLoop,
            """
while True:
    break
""",
        )

    def test_break_at_module_level(self):
        assert_error(BreakOutsideLoop, "break", "F701")

    def test_break_in_function_without_loop(self):
        assert_error(
            BreakOutsideLoop,
            """
def foo():
    break
""",
            "F701",
        )


class TestDefaultExceptNotLast:
    """Tests for F707: default except not last."""

    def test_bare_except_last_ok(self):
        assert_no_errors(
            DefaultExceptNotLast,
            """
try:
    pass
except TypeError:
    pass
except:
    pass
""",
        )

    def test_bare_except_not_last(self):
        assert_error(
            DefaultExceptNotLast,
            """
try:
    pass
except:
    pass
except TypeError:
    pass
""",
            "F707",
        )

    def test_specific_except_only_ok(self):
        assert_no_errors(
            DefaultExceptNotLast,
            """
try:
    pass
except TypeError:
    pass
except ValueError:
    pass
""",
        )

    def test_bare_except_alone_ok(self):
        assert_no_errors(
            DefaultExceptNotLast,
            """
try:
    pass
except:
    pass
""",
        )
