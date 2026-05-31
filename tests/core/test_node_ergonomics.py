"""Tests for Node ergonomics helpers (children_of_type, field_text, field_of_type, is_operator)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rude.core.node import Node, _NodeTypeMixin
from rude.core.node_types import NodeType
from rude.core.parser import parse_string
from rude.core.types import FileContext


def make_context(source: str) -> FileContext:
    """Create a FileContext from source string."""
    source_bytes = source.encode("utf-8")
    tree = parse_string(source)
    return FileContext(path=Path("<test>"), source=source_bytes, tree=tree)


class TestChildrenOfType:
    """Tests for Node.children_of_type(): direct named children filtered by type."""

    def test_filters_direct_children_by_string_type(self):
        source = "try:\n    pass\nexcept A:\n    pass\nexcept B:\n    pass\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        try_node = root.find_first("try_statement")
        assert try_node is not None

        excepts = try_node.children_of_type("except_clause")

        assert len(excepts) == 2
        assert all(c.type == "except_clause" for c in excepts)

    def test_filters_with_nodetype_enum(self):
        source = "try:\n    pass\nexcept A:\n    pass\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        try_node = root.find_first("try_statement")
        assert try_node is not None

        excepts = try_node.children_of_type(NodeType.EXCEPT_CLAUSE)

        assert len(excepts) == 1
        assert excepts[0].type == "except_clause"

    def test_accepts_iterable_of_types(self):
        source = "def foo():\n    x = 1\n    return x\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        func = root.find_first("function_definition")
        assert func is not None
        body = func.body
        assert body is not None

        results = body.children_of_type(("expression_statement", "return_statement"))

        types = {r.type for r in results}
        assert "return_statement" in types

    def test_returns_empty_when_no_match(self):
        source = "x = 1\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)

        results = root.children_of_type("function_definition")

        assert results == []

    def test_does_not_descend_into_descendants(self):
        # Outer try has 1 direct except (A); inner try also has 1 except (B).
        # children_of_type returns only direct children (1), unlike find() which recurses.
        source = "try:\n    try:\n        pass\n    except B:\n        pass\nexcept A:\n    pass\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        outer_try = root.find_first("try_statement")
        assert outer_try is not None

        direct = outer_try.children_of_type("except_clause")
        descendants = list(outer_try.find("except_clause"))

        assert len(direct) == 1
        assert len(descendants) == 2


class TestFieldText:
    """Tests for Node.field_text(): child_by_field + .text shortcut."""

    def test_returns_text_of_field_child(self):
        source = "def my_func(): pass\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        func = root.find_first("function_definition")
        assert func is not None

        assert func.field_text("name") == "my_func"

    def test_returns_none_when_field_absent(self):
        source = "x = 1\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)

        # module has no "name" field
        assert root.field_text("name") is None


class TestFieldOfType:
    """Tests for Node.field_of_type(): field child guarded by type."""

    def test_returns_node_when_type_matches(self):
        source = "def my_func(): pass\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        func = root.find_first("function_definition")
        assert func is not None

        name_node = func.field_of_type("name", "identifier")

        assert name_node is not None
        assert name_node.text == "my_func"

    def test_returns_none_when_type_mismatch(self):
        source = "def my_func(): pass\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        func = root.find_first("function_definition")
        assert func is not None

        # the "name" field exists with type "identifier", not "string"
        assert func.field_of_type("name", "string") is None

    def test_returns_none_when_field_absent(self):
        source = "x = 1\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)

        assert root.field_of_type("name", "identifier") is None


class TestIsOperator:
    """Tests for Node.is_operator(): matches against both .type and .text."""

    def test_matches_comparison_operator(self):
        source = "a == b\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        comp = root.find_first("comparison_operator")
        assert comp is not None

        matches = [c for c in comp.children if c.is_operator("==")]

        assert len(matches) == 1

    def test_matches_iterable_of_operators(self):
        source = "a != b\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        comp = root.find_first("comparison_operator")
        assert comp is not None

        matches = [c for c in comp.children if c.is_operator(("==", "!="))]

        assert len(matches) == 1

    def test_does_not_match_unrelated_identifier(self):
        source = "a == b\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        ident = root.find_first("identifier")
        assert ident is not None

        assert not ident.is_operator("==")
        assert not ident.is_operator(("==", "!="))


class TestAbstractDeclarations:
    """The bare ``_NodeTypeMixin`` declares ``type``, ``text``, ``named_children``
    and ``child_by_field`` as defensive stubs that raise ``NotImplementedError``.
    Concrete classes (Node, NodeProxy) must override them. These tests assert
    the documented contract.
    """

    def test_type_raises(self):
        m = _NodeTypeMixin()
        with pytest.raises(NotImplementedError):
            _ = m.type

    def test_text_raises(self):
        m = _NodeTypeMixin()
        with pytest.raises(NotImplementedError):
            _ = m.text

    def test_named_children_raises(self):
        m = _NodeTypeMixin()
        with pytest.raises(NotImplementedError):
            _ = m.named_children

    def test_child_by_field_raises(self):
        m = _NodeTypeMixin()
        with pytest.raises(NotImplementedError):
            m.child_by_field("name")


class TestDocstring:
    """Tests for Node.docstring(): extract docstring text from module/function/class."""

    def test_module_docstring(self):
        source = '"""mod doc"""\n'
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)

        assert root.docstring() == "mod doc"

    def test_function_docstring(self):
        source = 'def f():\n    """func doc"""\n    pass\n'
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        func = root.find_first("function_definition")
        assert func is not None

        assert func.docstring() == "func doc"

    def test_class_docstring(self):
        source = 'class C:\n    """cls doc"""\n    pass\n'
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        cls = root.find_first("class_definition")
        assert cls is not None

        assert cls.docstring() == "cls doc"

    def test_returns_none_when_no_docstring(self):
        source = "def f():\n    pass\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        func = root.find_first("function_definition")
        assert func is not None

        assert func.docstring() is None

    def test_returns_none_for_non_eligible_node(self):
        source = "x = 1\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        ident = root.find_first("identifier")
        assert ident is not None

        assert ident.docstring() is None

    def test_triple_single_quote_docstring(self):
        source = "def f():\n    '''triple single'''\n    pass\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        func = root.find_first("function_definition")
        assert func is not None

        assert func.docstring() == "triple single"

    def test_skips_leading_comment(self):
        source = 'def f():\n    # leading\n    """real doc"""\n'
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        func = root.find_first("function_definition")
        assert func is not None

        assert func.docstring() == "real doc"

    def test_returns_none_when_first_statement_is_not_string(self):
        source = "def f():\n    x = 1\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        func = root.find_first("function_definition")
        assert func is not None

        assert func.docstring() is None
