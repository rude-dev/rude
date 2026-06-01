"""Tests for statement rules (E701-E704, E722, E731, E741-E743)."""

from rude.rules.pycodestyle import (
    AmbiguousClassName,
    AmbiguousFunctionName,
    AmbiguousVariableName,
    BareExcept,
    LambdaAssignment,
    MultipleStatementsOnOneLineColon,
    MultipleStatementsOnOneLineDef,
    StatementEndsWithSemicolon,
)
from tests.conftest import check_source, fix_source


class TestMultipleStatementsOnOneLineColon:
    """Tests for E701: multiple statements on one line (colon)."""

    def test_if_on_one_line(self):
        source = "if x: print(x)"
        diagnostics = check_source(MultipleStatementsOnOneLineColon, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E701"

    def test_if_multiline_ok(self):
        source = """if x:
    print(x)"""
        diagnostics = check_source(MultipleStatementsOnOneLineColon, source)
        assert len(diagnostics) == 0


class TestMultipleStatementsOnOneLineDef:
    """Tests for E704: multiple statements on one line (def)."""

    def test_def_on_one_line(self):
        source = "def f(): return 1"
        diagnostics = check_source(MultipleStatementsOnOneLineDef, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E704"

    def test_def_multiline_ok(self):
        source = """def f():
    return 1"""
        diagnostics = check_source(MultipleStatementsOnOneLineDef, source)
        assert len(diagnostics) == 0


class TestBareExcept:
    """Tests for E722: bare except."""

    def test_bare_except(self):
        source = """try:
    pass
except:
    pass"""
        diagnostics = check_source(BareExcept, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E722"

    def test_except_exception_ok(self):
        source = """try:
    pass
except Exception:
    pass"""
        diagnostics = check_source(BareExcept, source)
        assert len(diagnostics) == 0


class TestLambdaAssignment:
    """Tests for E731: lambda assignment."""

    def test_lambda_assignment(self):
        source = "f = lambda x: x + 1"
        diagnostics = check_source(LambdaAssignment, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E731"

    def test_def_ok(self):
        source = """def f(x):
    return x + 1"""
        diagnostics = check_source(LambdaAssignment, source)
        assert len(diagnostics) == 0


class TestAmbiguousVariableName:
    """Tests for E741: ambiguous variable name."""

    def test_lowercase_l(self):
        source = "l = 1"
        diagnostics = check_source(AmbiguousVariableName, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E741"

    def test_uppercase_o(self):
        source = "O = 1"
        diagnostics = check_source(AmbiguousVariableName, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E741"

    def test_uppercase_i(self):
        source = "I = 1"
        diagnostics = check_source(AmbiguousVariableName, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E741"

    def test_normal_name_ok(self):
        source = "length = 1"
        diagnostics = check_source(AmbiguousVariableName, source)
        assert len(diagnostics) == 0


class TestAmbiguousClassName:
    """Tests for E742: ambiguous class name."""

    def test_class_i(self):
        source = """class I:
    pass"""
        diagnostics = check_source(AmbiguousClassName, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E742"

    def test_normal_class_ok(self):
        source = """class Index:
    pass"""
        diagnostics = check_source(AmbiguousClassName, source)
        assert len(diagnostics) == 0


class TestAmbiguousFunctionName:
    """Tests for E743: ambiguous function name."""

    def test_function_l(self):
        source = """def l():
    pass"""
        diagnostics = check_source(AmbiguousFunctionName, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E743"

    def test_normal_function_ok(self):
        source = """def length():
    pass"""
        diagnostics = check_source(AmbiguousFunctionName, source)
        assert len(diagnostics) == 0


class TestStatementEndsWithSemicolon:
    """Tests for E703: statement ends with a semicolon."""

    def test_autofix_preserves_utf8_string(self):
        source = 'x = "café";\n'
        expected = 'x = "café"\n'

        _, fixed = fix_source(StatementEndsWithSemicolon, source)

        assert fixed == expected, f"autofix corrupted UTF-8: got {fixed!r}"
