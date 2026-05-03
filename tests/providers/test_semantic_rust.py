"""
Tests for Rust SemanticModel implementation.

Tests the Rust/PyO3 implementation using the analyze_source function.
"""

from __future__ import annotations

import pytest

from rude._rust import SemanticModel
from rude.providers.semantic import (
    ScopeType,
    analyze_source,
)


@pytest.fixture
def simple_model() -> SemanticModel:
    """Get a SemanticModel for a simple module with one variable."""
    source = b"x = 1"
    return analyze_source(source)


@pytest.fixture
def function_model() -> SemanticModel:
    """Get a SemanticModel for a module with a function."""
    source = b"""
def foo(a, b):
    c = a + b
    return c
"""
    return analyze_source(source)


@pytest.fixture
def class_model() -> SemanticModel:
    """Get a SemanticModel for a module with a class."""
    source = b"""
class MyClass:
    def __init__(self, x):
        self.x = x
"""
    return analyze_source(source)


class TestAnalyzeSource:
    """Tests for the analyze_source function."""

    def test_basic_analysis(self) -> None:
        """Test basic source analysis."""
        model = analyze_source(b"x = 1")
        assert model is not None
        assert len(model.scopes) == 1  # Module scope
        assert model.module_scope == 0

    def test_empty_source(self) -> None:
        """Test analyzing empty source."""
        model = analyze_source(b"")
        assert len(model.scopes) == 1  # Module scope

    def test_module_with_binding(self, simple_model: SemanticModel) -> None:
        """Test module with a single binding."""
        assert len(simple_model.scopes) == 1
        assert len(simple_model.bindings) == 1
        assert simple_model.bindings[0].name == "x"


class TestRustSemanticModel:
    """Tests for Rust SemanticModel properties."""

    def test_module_scope(self, simple_model: SemanticModel) -> None:
        """Test module_scope property."""
        assert simple_model.module_scope == 0

    def test_scopes_property(self, function_model: SemanticModel) -> None:
        """Test scopes property returns all scopes."""
        scopes = function_model.scopes
        assert len(scopes) == 2  # Module + function

    def test_bindings_property(self, function_model: SemanticModel) -> None:
        """Test bindings property returns all bindings."""
        bindings = function_model.bindings
        # foo (function name) + a + b (params) + c (local)
        assert len(bindings) >= 4

    def test_lookup(self, simple_model: SemanticModel) -> None:
        """Test name lookup."""
        result = simple_model.lookup("x", 0)
        assert result == 0

        result = simple_model.lookup("y", 0)
        assert result is None

    def test_lookup_nested(self, function_model: SemanticModel) -> None:
        """Test name lookup through nested scopes."""
        # 'foo' is in module scope (0)
        result = function_model.lookup("foo", 0)
        assert result is not None

    def test_is_used(self, function_model: SemanticModel) -> None:
        """Test is_used method."""
        # Parameter 'a' and 'b' are used in the function body
        # Find the function scope (should be scope 1)
        _func_scope = function_model.scopes[1]

        # 'a' should be used (referenced in 'c = a + b')
        assert function_model.is_used("a", 1) is True
        assert function_model.is_used("b", 1) is True

    def test_tracking_lists(self) -> None:
        """Test unresolved, annotation_only, and declarations lists."""
        # Source with unresolved name
        model = analyze_source(b"print(x)")  # x is unresolved

        # Should have unresolved entries for 'print' and 'x'
        assert len(model.unresolved) >= 1

    def test_annotation_only(self) -> None:
        """Test annotation-only declarations are tracked."""
        model = analyze_source(b"x: int")

        # Should have annotation_only entry for 'x'
        assert len(model.annotation_only) == 1
        assert model.annotation_only[0].name == "x"

    def test_declarations(self) -> None:
        """Test global/nonlocal declarations are tracked."""
        source = b"""
def foo():
    global x
    nonlocal y
"""
        model = analyze_source(source)

        # Should have declarations for 'x' and 'y'
        assert len(model.declarations) == 2

        # Check is_global flag
        decl_names = {d.name: d.is_global for d in model.declarations}
        assert decl_names.get("x") is True  # global
        assert decl_names.get("y") is False  # nonlocal


class TestRustScope:
    """Tests for Rust Scope class."""

    def test_scope_type(self, simple_model: SemanticModel) -> None:
        """Test scope type property."""
        scope = simple_model.scopes[0]
        assert scope.type == ScopeType.MODULE
        assert scope.type_ == ScopeType.MODULE

    def test_function_scope_type(self, function_model: SemanticModel) -> None:
        """Test function scope type."""
        func_scope = function_model.scopes[1]
        assert func_scope.type == ScopeType.FUNCTION

    def test_class_scope_type(self, class_model: SemanticModel) -> None:
        """Test class scope type."""
        class_scope = class_model.scopes[1]
        assert class_scope.type == ScopeType.CLASS

    def test_scope_parent(self, function_model: SemanticModel) -> None:
        """Test scope parent relationship."""
        module_scope = function_model.scopes[0]
        func_scope = function_model.scopes[1]

        assert module_scope.parent == -1  # No parent
        assert func_scope.parent == 0  # Parent is module

    def test_scope_children(self, function_model: SemanticModel) -> None:
        """Test scope children relationship."""
        module_scope = function_model.scopes[0]

        # Module scope should have function as child
        assert 1 in module_scope.children

    def test_scope_bindings(self, simple_model: SemanticModel) -> None:
        """Test scope bindings dict."""
        scope = simple_model.scopes[0]
        assert "x" in scope.bindings

    def test_scope_globals_nonlocals(self) -> None:
        """Test scope globals and nonlocals sets."""
        source = b"""
def foo():
    global x
    nonlocal y
    x = 1
"""
        model = analyze_source(source)
        func_scope = model.scopes[1]

        assert "x" in func_scope.globals
        assert "y" in func_scope.nonlocals


class TestRustBinding:
    """Tests for Rust Binding class."""

    def test_binding_properties(self, simple_model: SemanticModel) -> None:
        """Test binding properties."""
        binding = simple_model.bindings[0]
        assert binding.name == "x"
        assert binding.scope == 0
        assert binding.line == 1
        assert binding.column == 0

    def test_binding_flag_import(self) -> None:
        """Test import binding flag."""
        model = analyze_source(b"import os")
        binding = model.bindings[0]

        assert binding.is_import is True
        assert binding.is_parameter is False

    def test_binding_flag_parameter(self, function_model: SemanticModel) -> None:
        """Test parameter binding flag."""
        # Find parameter 'a'
        param_bindings = [b for b in function_model.bindings if b.name == "a"]
        assert len(param_bindings) == 1

        binding = param_bindings[0]
        assert binding.is_parameter is True
        assert binding.is_import is False

    def test_binding_flag_global(self) -> None:
        """Test global binding flag."""
        source = b"""
def foo():
    global x
    x = 1
"""
        model = analyze_source(source)

        # Find the binding for 'x' in function scope
        x_bindings = [b for b in model.bindings if b.name == "x" and b.scope == 1]
        assert len(x_bindings) == 1
        assert x_bindings[0].is_global is True

    def test_binding_references(self) -> None:
        """Test binding references."""
        source = b"""
x = 1
y = x + x
"""
        model = analyze_source(source)

        # Find binding for 'x'
        x_binding = next(b for b in model.bindings if b.name == "x")

        # 'x' should have 2 references (used twice in y = x + x)
        assert len(x_binding.references) == 2

    def test_exception_handler_binding(self) -> None:
        """Test exception handler binding has valid_until_byte."""
        source = b"""
try:
    pass
except Exception as e:
    print(e)
"""
        model = analyze_source(source)

        # Find the exception handler binding
        e_bindings = [b for b in model.bindings if b.name == "e"]
        assert len(e_bindings) == 1

        binding = e_bindings[0]
        assert binding.is_exception_handler is True
        assert binding.valid_until_byte is not None


class TestComprehensions:
    """Tests for comprehension scope handling."""

    def test_list_comprehension(self) -> None:
        """Test list comprehension creates scope."""
        source = b"[x for x in range(10)]"
        model = analyze_source(source)

        # Module + comprehension scopes
        assert len(model.scopes) == 2
        assert model.scopes[1].type == ScopeType.COMPREHENSION

    def test_generator_expression(self) -> None:
        """Test generator expression creates scope."""
        source = b"(x for x in range(10))"
        model = analyze_source(source)

        assert len(model.scopes) == 2
        assert model.scopes[1].type == ScopeType.COMPREHENSION

    def test_walrus_operator(self) -> None:
        """Test walrus operator binds in enclosing scope."""
        source = b"""
if (n := 10):
    pass
"""
        model = analyze_source(source)

        # 'n' should be bound in module scope
        n_bindings = [b for b in model.bindings if b.name == "n"]
        assert len(n_bindings) == 1
        assert n_bindings[0].scope == 0  # Module scope


class TestImports:
    """Tests for import handling."""

    def test_simple_import(self) -> None:
        """Test simple import statement."""
        model = analyze_source(b"import os")
        assert len(model.bindings) == 1
        assert model.bindings[0].name == "os"
        assert model.bindings[0].is_import is True

    def test_import_alias(self) -> None:
        """Test import with alias."""
        model = analyze_source(b"import numpy as np")
        assert len(model.bindings) == 1
        assert model.bindings[0].name == "np"

    def test_from_import(self) -> None:
        """Test from import statement."""
        model = analyze_source(b"from os import path")
        assert len(model.bindings) == 1
        assert model.bindings[0].name == "path"

    def test_from_import_alias(self) -> None:
        """Test from import with alias."""
        model = analyze_source(b"from os import path as p")
        assert len(model.bindings) == 1
        assert model.bindings[0].name == "p"

    def test_dotted_import(self) -> None:
        """Test dotted import (import os.path)."""
        model = analyze_source(b"import os.path")
        # Should bind 'os' (the first part)
        assert len(model.bindings) == 1
        assert model.bindings[0].name == "os"


class TestStringLines:
    """Tests for string_lines property on SemanticModel."""

    def test_no_multiline_strings(self) -> None:
        """No multi-line strings -> empty."""
        source = b"x = 'hello'"
        model = analyze_source(source)
        assert model.string_lines == []

    def test_multiline_string(self) -> None:
        """Multi-line triple-quoted string -> interior lines."""
        source = b'x = """\nline 2\nline 3\n"""'
        model = analyze_source(source)
        lines = model.string_lines
        # String starts on line 1, ends on line 4
        # Interior lines are 2, 3, 4
        assert 2 in lines
        assert 3 in lines
        assert 4 in lines
        assert 1 not in lines

    def test_single_line_string_excluded(self) -> None:
        """Single-line strings should not produce any string_lines."""
        source = b"x = 'hello'\ny = 'world'"
        model = analyze_source(source)
        assert model.string_lines == []

    def test_node_count(self) -> None:
        """node_count should be positive."""
        source = b"def foo(): pass"
        model = analyze_source(source)
        assert model.node_count > 0


class TestNoqaLines:
    """Tests for noqa_lines property on SemanticModel."""

    def test_no_noqa(self) -> None:
        """No noqa comments -> empty dict."""
        source = b"x = 1"
        model = analyze_source(source)
        assert model.noqa_lines == {}

    def test_blanket_noqa(self) -> None:
        """Blanket noqa -> line maps to None."""
        source = b"x = 1  # noqa"
        model = analyze_source(source)
        noqa = model.noqa_lines
        assert 1 in noqa
        assert noqa[1] is None

    def test_specific_noqa(self) -> None:
        """Specific noqa -> line maps to list of codes."""
        source = b"x = 1  # noqa: E501, F401"
        model = analyze_source(source)
        noqa = model.noqa_lines
        assert 1 in noqa
        codes = noqa[1]
        assert codes is not None
        assert "E501" in codes
        assert "F401" in codes

    def test_noqa_case_insensitive(self) -> None:
        """noqa should be case-insensitive."""
        source = b"x = 1  # NOQA"
        model = analyze_source(source)
        assert 1 in model.noqa_lines
