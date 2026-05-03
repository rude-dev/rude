"""Tests for NodeType validation."""

from __future__ import annotations

from collections.abc import Iterator
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

import pytest

from rude.core.linter import Linter
from rude.core.node_types import VALID_NODE_TYPES, NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic

if TYPE_CHECKING:
    from rude.core.node import Node


class TestNodeType:
    def test_is_strenum(self):
        assert issubclass(NodeType, StrEnum)

    def test_backward_compat_with_strings(self):
        """StrEnum values compare equal to their string values."""
        assert NodeType.CALL == "call"  # type: ignore[comparison-overlap]
        assert NodeType.MODULE == "module"  # type: ignore[comparison-overlap]
        assert NodeType.FUNCTION_DEFINITION == "function_definition"  # type: ignore[comparison-overlap]

    def test_common_members_exist(self):
        assert hasattr(NodeType, "CALL")
        assert hasattr(NodeType, "MODULE")
        assert hasattr(NodeType, "ASSIGNMENT")
        assert hasattr(NodeType, "FUNCTION_DEFINITION")
        assert hasattr(NodeType, "CLASS_DEFINITION")
        assert hasattr(NodeType, "IMPORT_STATEMENT")
        assert hasattr(NodeType, "STRING")

    def test_importable_from_rude(self):
        from rude import NodeType as NT

        assert NT.CALL == "call"  # type: ignore[comparison-overlap]


class TestValidNodeTypes:
    def test_sourced_from_tree_sitter(self):
        """Generated constants match the live tree-sitter grammar."""
        from rude._rust import node_type_names

        ts_names = frozenset(node_type_names())
        assert ts_names == VALID_NODE_TYPES

    def test_derived_from_enum(self):
        assert frozenset(NodeType) == VALID_NODE_TYPES

    def test_contains_common_types(self):
        for t in (
            "call",
            "module",
            "assignment",
            "function_definition",
            "class_definition",
            "import_statement",
            "string",
        ):
            assert t in VALID_NODE_TYPES, f"{t!r} missing from VALID_NODE_TYPES"

    def test_is_frozenset(self):
        assert isinstance(VALID_NODE_TYPES, frozenset)

    def test_no_empty_strings(self):
        assert "" not in VALID_NODE_TYPES

    def test_all_lowercase_with_underscores(self):
        for t in VALID_NODE_TYPES:
            assert t == t.lower(), f"{t!r} is not lowercase"
            assert " " not in t, f"{t!r} contains spaces"


class _BadNodeTypeRule(Rule):
    code: ClassVar[str] = "TEST"
    message: ClassVar[str] = "test"
    node_types: ClassVar[set[str]] = {"calll"}  # type: ignore[assignment]  # typo — raw string still works

    def check(self, node: Node) -> Iterator[Diagnostic]:
        return iter(())


class _GoodRule(Rule):
    code: ClassVar[str] = "TEST2"
    message: ClassVar[str] = "test"
    node_types = {NodeType.CALL}  # new style

    def check(self, node: Node) -> Iterator[Diagnostic]:
        return iter(())


class _GoodRuleRawString(Rule):
    code: ClassVar[str] = "TEST3"
    message: ClassVar[str] = "test"
    node_types: ClassVar[set[str]] = {"call"}  # type: ignore[assignment]  # old style — still valid

    def check(self, node: Node) -> Iterator[Diagnostic]:
        return iter(())


class TestLinterValidation:
    def test_register_invalid_node_type_raises(self):
        linter = Linter()
        with pytest.raises(ValueError, match=r"Unknown node type.*calll"):
            linter.register(_BadNodeTypeRule())

    def test_register_valid_node_type_ok(self):
        linter = Linter()
        linter.register(_GoodRule())  # should not raise

    def test_register_raw_string_still_works(self):
        linter = Linter()
        linter.register(_GoodRuleRawString())  # backward compat
