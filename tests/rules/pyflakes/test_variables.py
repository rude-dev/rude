"""Tests for variable rules (F841, F842, F824)."""

from rude.rules.pyflakes import UnusedAnnotation, UnusedIndirectAssignment, UnusedVariable
from tests.conftest import assert_error, assert_error_count, assert_no_errors


class TestUnusedVariable:
    """Tests for F841: local variable assigned but never used."""

    def test_basic_unused_variable(self):
        """Unused variable in a function should trigger F841."""
        assert_error(
            UnusedVariable,
            """
def foo():
    x = 1
""",
            "F841",
        )

    def test_used_variable_ok(self):
        """Variable that is used should not trigger F841."""
        assert_no_errors(
            UnusedVariable,
            """
def foo():
    x = 1
    print(x)
""",
        )

    def test_underscore_ok(self):
        """Underscore variable should not trigger F841."""
        assert_no_errors(
            UnusedVariable,
            """
def foo():
    _ = 1
""",
        )

    def test_augmented_assign(self):
        """Augmented assignment to otherwise unused variable should trigger F841."""
        assert_error(
            UnusedVariable,
            """
def foo():
    x = 1
    x += 1
""",
            "F841",
        )

    def test_function_parameter_ok(self):
        """Function parameters should not trigger F841."""
        assert_no_errors(
            UnusedVariable,
            """
def foo(x):
    pass
""",
        )

    def test_loop_variable_used_ok(self):
        """Loop variable that is used should not trigger F841."""
        assert_no_errors(
            UnusedVariable,
            """
def foo():
    for x in range(10):
        print(x)
""",
        )

    def test_multiple_unused(self):
        """Multiple unused variables should each trigger F841."""
        diagnostics = assert_error_count(
            UnusedVariable,
            """
def foo():
    x = 1
    y = 2
    z = 3
    return z
""",
            2,
        )
        names = [d.message for d in diagnostics]
        assert any("'x'" in m for m in names)
        assert any("'y'" in m for m in names)


class TestUnusedAnnotation:
    """Tests for F842: variable annotated but never used."""

    def test_annotation_with_assignment_ok(self):
        """Annotation with assignment should not trigger F842."""
        assert_no_errors(
            UnusedAnnotation,
            """
def foo():
    x: int = 1
    print(x)
""",
        )

    def test_annotation_only_unused(self):
        """Annotation without assignment or use should trigger F842."""
        assert_error(
            UnusedAnnotation,
            """
def foo():
    x: int
""",
            "F842",
        )

    def test_annotation_used_without_assignment(self):
        """Annotation used without assignment should not trigger F842."""
        assert_no_errors(
            UnusedAnnotation,
            """
def foo():
    x: int
    print(x)
""",
        )

    def test_class_annotation_ok(self):
        """Class-level annotations should not trigger F842 (different scope)."""
        assert_no_errors(
            UnusedAnnotation,
            """
class Bar:
    x: int
""",
        )

    def test_multiple_annotations(self):
        """Multiple unused annotations should each trigger F842."""
        diagnostics = assert_error_count(
            UnusedAnnotation,
            """
def foo():
    x: int
    y: str
    z: float = 1.0
""",
            2,
        )
        names = [d.message for d in diagnostics]
        assert any("'x'" in m for m in names)
        assert any("'y'" in m for m in names)

    def test_annotation_assigned_later(self):
        """Annotation that is assigned later should not trigger F842."""
        assert_no_errors(
            UnusedAnnotation,
            """
def foo():
    x: int
    x = 1
    print(x)
""",
        )

    def test_async_function(self):
        """F842 should work in async functions."""
        assert_error(
            UnusedAnnotation,
            """
async def foo():
    x: int
""",
            "F842",
        )


class TestUnusedIndirectAssignment:
    """Tests for F824: global/nonlocal declared but never assigned."""

    def test_global_assigned_ok(self):
        """Global that is assigned should not trigger F824."""
        assert_no_errors(
            UnusedIndirectAssignment,
            """
x = 1

def foo():
    global x
    x = 2
""",
        )

    def test_global_not_assigned(self):
        """Global that is only read should trigger F824."""
        assert_error(
            UnusedIndirectAssignment,
            """
x = 1

def foo():
    global x
    print(x)
""",
            "F824",
        )

    def test_nonlocal_assigned_ok(self):
        """Nonlocal that is assigned should not trigger F824."""
        assert_no_errors(
            UnusedIndirectAssignment,
            """
def outer():
    x = 1
    def inner():
        nonlocal x
        x = 2
""",
        )

    def test_nonlocal_not_assigned(self):
        """Nonlocal that is only read should trigger F824."""
        assert_error(
            UnusedIndirectAssignment,
            """
def outer():
    x = 1
    def inner():
        nonlocal x
        print(x)
""",
            "F824",
        )

    def test_augmented_assignment_ok(self):
        """Augmented assignment counts as assignment."""
        assert_no_errors(
            UnusedIndirectAssignment,
            """
x = 1

def foo():
    global x
    x += 1
""",
        )

    def test_multiple_globals(self):
        """Multiple unused globals should each trigger F824."""
        diagnostics = assert_error_count(
            UnusedIndirectAssignment,
            """
x = 1
y = 2

def foo():
    global x, y
    print(x, y)
""",
            2,
        )
        messages = [d.message for d in diagnostics]
        assert any("'x'" in m for m in messages)
        assert any("'y'" in m for m in messages)

    def test_async_function(self):
        """F824 should work in async functions."""
        assert_error(
            UnusedIndirectAssignment,
            """
x = 1

async def foo():
    global x
    print(x)
""",
            "F824",
        )

    def test_global_message_format(self):
        """Verify the message includes 'global' for global statements."""
        diagnostics = assert_error(
            UnusedIndirectAssignment,
            """
x = 1

def foo():
    global x
""",
            "F824",
        )
        assert "global" in diagnostics[0].message

    def test_nonlocal_message_format(self):
        """Verify the message includes 'nonlocal' for nonlocal statements."""
        diagnostics = assert_error(
            UnusedIndirectAssignment,
            """
def outer():
    x = 1
    def inner():
        nonlocal x
""",
            "F824",
        )
        assert "nonlocal" in diagnostics[0].message
