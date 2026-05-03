"""Tests for complexity rules (C901)."""

from rude.rules.mccabe import FunctionTooComplex
from tests.conftest import check_source


class TestFunctionTooComplex:
    """Tests for C901: function is too complex."""

    def test_simple_function_ok(self):
        source = """def simple():
    return 1"""
        diagnostics = check_source(FunctionTooComplex, source)
        assert len(diagnostics) == 0

    def test_complex_function(self):
        # Complexity = 12: 1 base + 3 if + 2 elif + 1 for + 1 if + 1 elif + 1 while + 1 if + 1 if
        source = """def complex_function(x, y, z):
    if x > 0:
        if x > 10:
            return "big"
        elif x > 5:
            return "medium"
        else:
            return "small"

    for i in range(y):
        if i % 2 == 0:
            print("even")
        elif i % 3 == 0:
            print("divisible by 3")

    while z > 0:
        if z % 2:
            print(z)
        z -= 1

    if x:
        if y:
            return z"""
        diagnostics = check_source(FunctionTooComplex, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "C901"
        assert "complex_function" in diagnostics[0].message

    def test_complexity_at_threshold(self):
        # Complexity = 10 (1 base + 9 if statements)
        source = """def at_threshold(x):
    if x == 1:
        pass
    if x == 2:
        pass
    if x == 3:
        pass
    if x == 4:
        pass
    if x == 5:
        pass
    if x == 6:
        pass
    if x == 7:
        pass
    if x == 8:
        pass
    if x == 9:
        pass"""
        diagnostics = check_source(FunctionTooComplex, source)
        assert len(diagnostics) == 0

    def test_complexity_above_threshold(self):
        # Complexity = 11 (1 base + 10 if statements)
        source = """def above_threshold(x):
    if x == 1:
        pass
    if x == 2:
        pass
    if x == 3:
        pass
    if x == 4:
        pass
    if x == 5:
        pass
    if x == 6:
        pass
    if x == 7:
        pass
    if x == 8:
        pass
    if x == 9:
        pass
    if x == 10:
        pass"""
        diagnostics = check_source(FunctionTooComplex, source)
        assert len(diagnostics) == 1

    def test_nested_function_counted_separately(self):
        source = """def outer():
    def inner():
        if x:
            if y:
                if z:
                    pass
    return inner"""
        diagnostics = check_source(FunctionTooComplex, source)
        # Outer has complexity 1, inner is not counted in outer
        assert len(diagnostics) == 0

    def test_async_function(self):
        source = """async def async_complex(x):
    if x == 1:
        pass
    if x == 2:
        pass
    if x == 3:
        pass
    if x == 4:
        pass
    if x == 5:
        pass
    if x == 6:
        pass
    if x == 7:
        pass
    if x == 8:
        pass
    if x == 9:
        pass
    if x == 10:
        pass"""
        diagnostics = check_source(FunctionTooComplex, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "C901"
