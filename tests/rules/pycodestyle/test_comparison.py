"""Tests for comparison rules (E711-E714, E721)."""

from rude.rules.pycodestyle import (
    ComparisonToNone,
    ComparisonToTrueFalse,
    NotInTest,
    NotIsTest,
    TypeComparison,
)
from tests.conftest import check_source


class TestComparisonToNone:
    """Tests for E711: comparison to None."""

    def test_equality_to_none(self):
        source = "x == None"
        diagnostics = check_source(ComparisonToNone, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E711"

    def test_inequality_to_none(self):
        source = "x != None"
        diagnostics = check_source(ComparisonToNone, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E711"

    def test_is_none_ok(self):
        source = "x is None"
        diagnostics = check_source(ComparisonToNone, source)
        assert len(diagnostics) == 0

    def test_is_not_none_ok(self):
        source = "x is not None"
        diagnostics = check_source(ComparisonToNone, source)
        assert len(diagnostics) == 0


class TestComparisonToTrueFalse:
    """Tests for E712: comparison to True/False."""

    def test_equality_to_true(self):
        source = "x == True"
        diagnostics = check_source(ComparisonToTrueFalse, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E712"

    def test_equality_to_false(self):
        source = "x == False"
        diagnostics = check_source(ComparisonToTrueFalse, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E712"

    def test_is_true_ok(self):
        source = "x is True"
        diagnostics = check_source(ComparisonToTrueFalse, source)
        assert len(diagnostics) == 0

    def test_boolean_expression_ok(self):
        source = "if x:"
        diagnostics = check_source(ComparisonToTrueFalse, source)
        assert len(diagnostics) == 0


class TestNotInTest:
    """Tests for E713: not in test."""

    def test_not_x_in_y(self):
        source = "not x in [1, 2, 3]"
        diagnostics = check_source(NotInTest, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E713"

    def test_x_not_in_y_ok(self):
        source = "x not in [1, 2, 3]"
        diagnostics = check_source(NotInTest, source)
        assert len(diagnostics) == 0


class TestNotIsTest:
    """Tests for E714: not is test."""

    def test_not_x_is_y(self):
        source = "not x is None"
        diagnostics = check_source(NotIsTest, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E714"

    def test_x_is_not_y_ok(self):
        source = "x is not None"
        diagnostics = check_source(NotIsTest, source)
        assert len(diagnostics) == 0


class TestTypeComparison:
    """Tests for E721: type comparison."""

    def test_type_equality(self):
        source = "type(x) == int"
        diagnostics = check_source(TypeComparison, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E721"

    def test_type_is_ok(self):
        # 'is' is intentional exact-type check, not flagged (matches pycodestyle)
        source = "type(x) is int"
        diagnostics = check_source(TypeComparison, source)
        assert len(diagnostics) == 0

    def test_isinstance_ok(self):
        source = "isinstance(x, int)"
        diagnostics = check_source(TypeComparison, source)
        assert len(diagnostics) == 0
