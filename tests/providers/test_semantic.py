"""
Tests for arena-based semantic model.

Tests the SemanticModel, Scope, and Binding classes to ensure
the Rust implementation works correctly.
"""

from __future__ import annotations

from pathlib import Path

from rude.core.node import Node
from rude.core.parser import parse
from rude.core.types import FileContext
from rude.providers import (
    NO_SCOPE,
    ScopeProvider,
    ScopeType,
)


def get_context(source: str) -> FileContext:
    """Parse source and return FileContext."""
    source_bytes = source.encode("utf-8")
    tree = parse(source_bytes)
    return FileContext(path=Path("<string>"), source=source_bytes, tree=tree)


def get_scope_provider(source: str) -> ScopeProvider:
    """Parse source and return ScopeProvider."""
    ctx = get_context(source)
    provider = ScopeProvider()
    provider.compute(ctx)
    return provider


# Note: TestSemanticModelBasics was removed because SemanticModel is now
# immutable and constructed entirely by the Rust analyzer via analyze_source().
# The old mutable API (push_scope, add_binding, etc.) no longer exists.


class TestScopeProvider:
    """Tests for ScopeProvider."""

    def test_module_scope(self) -> None:
        """Test module_scope property."""
        provider = get_scope_provider("x = 1")
        model = provider.model

        assert model.module_scope != NO_SCOPE
        assert model.scopes[model.module_scope].type == ScopeType.MODULE

    def test_scope_for(self) -> None:
        """Test scope_for method."""
        source = """
def foo():
    x = 1
"""
        ctx = get_context(source)
        provider = ScopeProvider()
        provider.compute(ctx)
        model = provider.model

        root = Node(ctx.tree.root_node, ctx)
        # Find the x identifier inside the function
        for ident in root.find("identifier"):
            if ident.text == "x":
                scope_id = model.scope_for(ident)
                assert scope_id != NO_SCOPE
                assert model.scopes[scope_id].type == ScopeType.FUNCTION
                break

    def test_scope_at(self) -> None:
        """Test scope_at method."""
        source = """
def foo():
    pass
"""
        ctx = get_context(source)
        provider = ScopeProvider()
        provider.compute(ctx)
        model = provider.model

        root = Node(ctx.tree.root_node, ctx)
        func_node = next(root.find("function_definition"))
        scope_id = model.scope_at(func_node)

        assert scope_id != NO_SCOPE
        assert model.scopes[scope_id].type == ScopeType.FUNCTION


class TestBindings:
    """Tests for binding properties."""

    def test_is_import_property(self) -> None:
        """Test binding is_import property."""
        provider = get_scope_provider("import os")
        model = provider.model
        module_scope = model.scopes[model.module_scope]

        binding_id = module_scope.bindings["os"]
        binding = model.bindings[binding_id]
        assert binding.is_import is True

    def test_is_parameter_property(self) -> None:
        """Test binding is_parameter property."""
        source = """
def foo(x):
    pass
"""
        provider = get_scope_provider(source)
        model = provider.model
        func_scope = model.scopes[model.module_scope].children[0]
        func_scope_data = model.scopes[func_scope]

        binding_id = func_scope_data.bindings["x"]
        binding = model.bindings[binding_id]
        assert binding.is_parameter is True

    def test_is_global_property(self) -> None:
        """Test binding is_global property."""
        source = """
x = 1

def foo():
    global x
    x = 2
"""
        provider = get_scope_provider(source)
        model = provider.model
        func_scope = model.scopes[model.module_scope].children[0]
        func_scope_data = model.scopes[func_scope]

        binding_id = func_scope_data.bindings["x"]
        binding = model.bindings[binding_id]
        assert binding.is_global is True

    def test_is_exception_handler_property(self) -> None:
        """Test binding is_exception_handler property."""
        source = """
try:
    pass
except Exception as e:
    pass
"""
        provider = get_scope_provider(source)
        model = provider.model
        module_scope = model.scopes[model.module_scope]

        binding_id = module_scope.bindings["e"]
        binding = model.bindings[binding_id]
        assert binding.is_exception_handler is True
        assert binding.valid_until_byte is not None


class TestScopeProperties:
    """Tests for scope properties."""

    def test_globals_property(self) -> None:
        """Test scope globals property."""
        source = """
x = 1

def foo():
    global x
    x = 2
"""
        provider = get_scope_provider(source)
        model = provider.model
        func_scope = model.scopes[model.module_scope].children[0]
        func_scope_data = model.scopes[func_scope]

        assert "x" in func_scope_data.globals

    def test_nonlocals_property(self) -> None:
        """Test scope nonlocals property."""
        source = """
def outer():
    x = 1
    def inner():
        nonlocal x
        x = 2
"""
        provider = get_scope_provider(source)
        model = provider.model
        outer_scope = model.scopes[model.module_scope].children[0]
        inner_scope = model.scopes[outer_scope].children[0]
        inner_scope_data = model.scopes[inner_scope]

        assert "x" in inner_scope_data.nonlocals

    def test_is_used_method(self) -> None:
        """Test is_used method."""
        source = """
x = 1
y = 2
print(x)
"""
        provider = get_scope_provider(source)
        model = provider.model

        assert model.is_used("x", model.module_scope) is True
        assert model.is_used("y", model.module_scope) is False


class TestComprehensionScopes:
    """Tests for comprehension scope handling."""

    def test_list_comprehension_scope(self) -> None:
        """Test list comprehension creates scope."""
        source = "[x for x in items]"
        provider = get_scope_provider(source)
        model = provider.model
        module_scope = model.scopes[model.module_scope]

        assert len(module_scope.children) == 1
        comp_scope = model.scopes[module_scope.children[0]]
        assert comp_scope.type == ScopeType.COMPREHENSION
        assert "x" in comp_scope.bindings

    def test_walrus_operator_scope(self) -> None:
        """Test walrus operator binds in parent scope (PEP 572)."""
        source = "[y for x in items if (y := x)]"
        provider = get_scope_provider(source)
        model = provider.model
        module_scope = model.scopes[model.module_scope]

        # y should be bound in module scope, not comprehension scope
        assert "y" in module_scope.bindings


class TestImportBindings:
    """Tests for import binding handling."""

    def test_import_statement(self) -> None:
        """Test basic import statement."""
        provider = get_scope_provider("import os")
        model = provider.model
        module_scope = model.scopes[model.module_scope]

        assert "os" in module_scope.bindings
        binding = model.bindings[module_scope.bindings["os"]]
        assert binding.is_import is True

    def test_import_dotted(self) -> None:
        """Test dotted import binds first component."""
        provider = get_scope_provider("import os.path")
        model = provider.model
        module_scope = model.scopes[model.module_scope]

        assert "os" in module_scope.bindings
        assert "path" not in module_scope.bindings

    def test_from_import(self) -> None:
        """Test from import statement."""
        provider = get_scope_provider("from os import path")
        model = provider.model
        module_scope = model.scopes[model.module_scope]

        assert "path" in module_scope.bindings
        assert "os" not in module_scope.bindings


class TestLambdaScopes:
    """Tests for lambda scope handling."""

    def test_lambda_scope(self) -> None:
        """Test lambda creates function scope."""
        source = "f = lambda x: x + 1"
        provider = get_scope_provider(source)
        model = provider.model
        module_scope = model.scopes[model.module_scope]

        assert len(module_scope.children) == 1
        lambda_scope = model.scopes[module_scope.children[0]]
        assert lambda_scope.type == ScopeType.FUNCTION
        assert "x" in lambda_scope.bindings
        binding = model.bindings[lambda_scope.bindings["x"]]
        assert binding.is_parameter is True
