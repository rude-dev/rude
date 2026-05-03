"""Tests for metadata_dependencies contract enforcement.

Rules that depend on ScopeProvider must declare it in metadata_dependencies.
If they forget, the batch/streaming path will not trigger semantic analysis
and the rule silently gets no model.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar

from rude.core.linter import Linter
from rude.core.node import Node
from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Severity
from rude.providers import ScopeProvider


class _RuleWithDeps(Rule):
    """Rule that correctly declares ScopeProvider dependency."""

    code: ClassVar[str] = "TEST01"
    message: ClassVar[str] = "test rule with deps"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.MODULE}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        model = node.ctx.get_metadata(ScopeProvider).model
        # Simply verify we got a model with scopes
        if len(model.scopes) > 0:
            yield self.diagnostic(node)


class _RuleWithoutDeps(Rule):
    """Rule that forgets to declare ScopeProvider dependency."""

    code: ClassVar[str] = "TEST02"
    message: ClassVar[str] = "test rule without deps"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.MODULE}
    # NOTE: metadata_dependencies NOT declared

    def check(self, node: Node) -> Iterator[Diagnostic]:
        model = node.ctx.get_metadata(ScopeProvider).model
        if len(model.scopes) > 0:
            yield self.diagnostic(node)


class TestMetadataDependencies:
    """Verify that metadata_dependencies declaration affects behavior."""

    def test_rule_with_declared_deps_gets_model(self) -> None:
        """A rule that declares ScopeProvider gets a valid model."""
        linter = Linter()
        linter.register(_RuleWithDeps())
        diags = list(linter.check_source("x = 1\n"))
        assert any(d.code == "TEST01" for d in diags)

    def test_rule_without_deps_still_works_in_check_source(self) -> None:
        """check_source uses lazy computation, so it works even without declaration."""
        linter = Linter()
        linter.register(_RuleWithoutDeps())
        # check_source uses the single-file path with lazy metadata
        diags = list(linter.check_source("x = 1\n"))
        assert any(d.code == "TEST02" for d in diags)
