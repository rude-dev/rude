"""Tests for public utils helpers (ImportAlias, iter_import_aliases)."""

from __future__ import annotations

from pathlib import Path

from rude.core.node import Node
from rude.core.parser import parse_string
from rude.core.types import FileContext
from rude.utils import ImportAlias, iter_import_aliases


def _first_import(source: str) -> Node:
    source_bytes = source.encode("utf-8")
    tree = parse_string(source)
    ctx = FileContext(path=Path("<test>"), source=source_bytes, tree=tree)
    root = Node(ctx.tree.root_node, ctx)
    node = next((c for c in root.named_children if c.is_import), None)
    assert node is not None
    return node


class TestImportAlias:
    """Tests for the ImportAlias NamedTuple."""

    def test_fields(self):
        assert ImportAlias._fields == ("full_name", "alias", "is_from")

    def test_equality(self):
        assert ImportAlias("os", None, False) == ImportAlias("os", None, False)
        assert ImportAlias("os", None, False) != ImportAlias("os", "o", False)


class TestIterImportAliases:
    """Tests for iter_import_aliases() across the three import node types."""

    def test_plain_import(self):
        aliases = list(iter_import_aliases(_first_import("import os\n")))
        assert aliases == [ImportAlias("os", None, False)]

    def test_dotted_import(self):
        aliases = list(iter_import_aliases(_first_import("import os.path\n")))
        assert aliases == [ImportAlias("os.path", None, False)]

    def test_import_with_alias(self):
        aliases = list(iter_import_aliases(_first_import("import os as o\n")))
        assert aliases == [ImportAlias("os", "o", False)]

    def test_multiple_plain_imports(self):
        aliases = list(iter_import_aliases(_first_import("import a, b as B\n")))
        assert aliases == [
            ImportAlias("a", None, False),
            ImportAlias("b", "B", False),
        ]

    def test_from_import(self):
        aliases = list(iter_import_aliases(_first_import("from os import path\n")))
        assert aliases == [ImportAlias("os.path", None, True)]

    def test_from_import_with_alias(self):
        aliases = list(iter_import_aliases(_first_import("from os import path as p\n")))
        assert aliases == [ImportAlias("os.path", "p", True)]

    def test_from_import_multiple(self):
        aliases = list(iter_import_aliases(_first_import("from a.b import c, d\n")))
        assert aliases == [
            ImportAlias("a.b.c", None, True),
            ImportAlias("a.b.d", None, True),
        ]

    def test_future_import(self):
        aliases = list(iter_import_aliases(_first_import("from __future__ import annotations\n")))
        assert aliases == [ImportAlias("__future__.annotations", None, True)]

    def test_relative_import_dot_only(self):
        aliases = list(iter_import_aliases(_first_import("from . import x\n")))
        assert aliases == [ImportAlias(".x", None, True)]

    def test_relative_import_with_module(self):
        aliases = list(iter_import_aliases(_first_import("from ..pkg import y\n")))
        assert aliases == [ImportAlias("..pkg.y", None, True)]

    def test_non_import_node_yields_nothing(self):
        source = "x = 1\n"
        source_bytes = source.encode("utf-8")
        tree = parse_string(source)
        ctx = FileContext(path=Path("<test>"), source=source_bytes, tree=tree)
        root = Node(ctx.tree.root_node, ctx)
        assignment = root.find_first("assignment")
        assert assignment is not None

        assert list(iter_import_aliases(assignment)) == []
