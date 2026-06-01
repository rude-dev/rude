"""Tests for Node wrapper."""

from __future__ import annotations

from pathlib import Path

from rude.core.node import Node
from rude.core.parser import parse_string
from rude.core.types import FileContext


def make_context(source: str) -> FileContext:
    """Create a FileContext from source string."""
    source_bytes = source.encode("utf-8")
    tree = parse_string(source)
    return FileContext(path=Path("<test>"), source=source_bytes, tree=tree)


class TestWalk:
    """Tests for Node.walk() using TreeCursor."""

    def test_walk_returns_all_nodes(self):
        """walk() returns all nodes in the tree."""
        source = "x = 1"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)

        nodes = list(root.walk())
        types = [n.type for n in nodes]

        # Should include root (module) and all descendants
        assert "module" in types
        assert "expression_statement" in types
        assert "assignment" in types
        assert "identifier" in types
        assert "integer" in types

    def test_walk_depth_first_order(self):
        """walk() traverses depth-first, left-to-right."""
        source = "a = 1\nb = 2"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)

        nodes = list(root.walk())
        types = [n.type for n in nodes]

        # module is first
        assert types[0] == "module"

        # expression_statements should appear in order
        expr_indices = [i for i, t in enumerate(types) if t == "expression_statement"]
        assert len(expr_indices) == 2
        assert expr_indices[0] < expr_indices[1]

    def test_walk_yields_root(self):
        """walk() starts with the node itself."""
        source = "pass"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)

        nodes = list(root.walk())

        assert nodes[0] == root

    def test_walk_subtree(self):
        """walk() from a subtree only yields descendants of that node."""
        source = "if True:\n    x = 1"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)

        # Find the if_statement
        if_node = root.find_first("if_statement")
        assert if_node is not None

        walked = list(if_node.walk())
        types = [n.type for n in walked]

        # Should not include module
        assert "module" not in types
        # Should include if_statement as first
        assert types[0] == "if_statement"
        # Should include descendants
        assert "block" in types
        assert "assignment" in types

    def test_walk_leaf_node(self):
        """walk() on a leaf node yields just that node."""
        source = "x"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)

        # Find the identifier leaf
        ident = root.find_first("identifier")
        assert ident is not None

        walked = list(ident.walk())

        assert len(walked) == 1
        assert walked[0] == ident

    def test_walk_nested_structure(self):
        """walk() handles deeply nested structures correctly."""
        source = "if a:\n    if b:\n        if c:\n            pass"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)

        nodes = list(root.walk())
        if_nodes = [n for n in nodes if n.type == "if_statement"]

        # Should find all 3 if statements
        assert len(if_nodes) == 3
        # Outer if comes before inner ifs
        assert nodes.index(if_nodes[0]) < nodes.index(if_nodes[1])
        assert nodes.index(if_nodes[1]) < nodes.index(if_nodes[2])

    def test_walk_function_with_args(self):
        """walk() traverses function definitions with parameters."""
        source = "def foo(a, b=1):\n    return a + b"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)

        nodes = list(root.walk())
        types = [n.type for n in nodes]

        assert "function_definition" in types
        assert "parameters" in types
        assert "identifier" in types
        assert "return_statement" in types
        assert "binary_operator" in types

    def test_walk_preserves_node_identity(self):
        """walk() creates valid Node wrappers for each node."""
        source = "x = 1 + 2"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)

        for node in root.walk():
            # Each node should have valid properties
            assert node.type is not None
            assert node.line >= 1
            assert node.column >= 0
            # Text should be extractable
            assert isinstance(node.text, str)


class TestLocationColumns:
    """Columns are character offsets (LSP convention), not byte offsets."""

    def test_column_is_character_offset_on_utf8_line(self):
        # "café = 1": `1` is at character column 7, byte column 8 (é = 2 UTF-8 bytes).
        source = "café = 1\n"
        ctx = make_context(source)
        root = Node(ctx.tree.root_node, ctx)
        assignment = root.find_first("assignment")
        assert assignment is not None
        right = assignment.child_by_field("right")
        assert right is not None

        assert right.location.column == 7
