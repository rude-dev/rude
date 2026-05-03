"""Tests for annotation rules (F722)."""

from rude.rules.pyflakes import ForwardAnnotationSyntaxError
from tests.conftest import assert_error, assert_no_errors


class TestForwardAnnotationSyntaxError:
    """Tests for F722: syntax error in forward annotation."""

    def test_valid_forward_annotation_ok(self):
        assert_no_errors(
            ForwardAnnotationSyntaxError,
            """
x: "List[int]"
""",
        )

    def test_valid_return_annotation_ok(self):
        assert_no_errors(
            ForwardAnnotationSyntaxError,
            """
def foo() -> "str":
    pass
""",
        )

    def test_invalid_forward_annotation(self):
        assert_error(
            ForwardAnnotationSyntaxError,
            """
x: "List[int"
""",
            "F722",
        )

    def test_invalid_return_annotation(self):
        assert_error(
            ForwardAnnotationSyntaxError,
            """
def foo() -> "List[":
    pass
""",
            "F722",
        )

    def test_regular_string_ok(self):
        # Regular strings (not in annotation context) should not trigger
        assert_no_errors(
            ForwardAnnotationSyntaxError,
            """
x = "List[int"
""",
        )

    def test_docstring_ok(self):
        # Docstrings should not trigger
        assert_no_errors(
            ForwardAnnotationSyntaxError,
            '''
def foo():
    """This is a docstring with List[int syntax."""
    pass
''',
        )
