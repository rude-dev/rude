"""
Variable-related rules.

F824: UnusedIndirectAssignment - global/nonlocal declared but never assigned locally
F842: UnusedAnnotation - variable annotated but never used or assigned
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Location, Severity
from rude.providers import ScopeProvider

if TYPE_CHECKING:
    from rude.core.node import Node


class UnusedAnnotation(Rule):
    """
    F842: Variable is annotated but never used or assigned a value.

    Rationale: An annotation without an assignment or use is dead code
    that should be removed or completed.

    Example::

        # Bad
        def foo():
            x: int       # F842 - x is never used or assigned

        # Good
        def foo():
            x: int = 1

    Optimized: Uses pre-computed unused_annotations from Rust SemanticModel.
    """

    code: ClassVar[str] = "F842"
    message: ClassVar[str] = "local variable '{name}' is annotated but never used"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.MODULE}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        """Find annotations without assignments using pre-computed list from Rust."""
        scope_prov: ScopeProvider = node.ctx.get_metadata(ScopeProvider)
        model = scope_prov.model

        # Iterate over pre-computed unused annotations
        for entry in model.unused_annotations:
            yield Diagnostic(
                code=self.code,
                message=self.message.format(name=entry.name),
                location=Location(line=entry.line, column=entry.column),
                severity=self.severity,
            )


class UnusedIndirectAssignment(Rule):
    """
    F824: Global or nonlocal declaration but name is never assigned in this scope.

    Rationale: A ``global`` or ``nonlocal`` declaration without a
    subsequent assignment is unnecessary and misleading.

    Example::

        # Bad
        def foo():
            global x   # F824 - x is never assigned in foo()
            print(x)

        # Good
        def foo():
            print(x)   # just read the global directly

    Optimized: Uses pre-computed unused_declarations from Rust SemanticModel.
    """

    code: ClassVar[str] = "F824"
    message: ClassVar[str] = "local variable '{name}' is declared {kind} but never assigned"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.MODULE}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        """Check for global/nonlocal declarations using pre-computed list from Rust."""
        scope_prov: ScopeProvider = node.ctx.get_metadata(ScopeProvider)
        model = scope_prov.model

        # Iterate over pre-computed unused declarations
        for decl in model.unused_declarations:
            kind = "global" if decl.is_global else "nonlocal"
            yield Diagnostic(
                code=self.code,
                message=self.message.format(name=decl.name, kind=kind),
                location=Location(line=decl.line, column=decl.column),
                severity=self.severity,
            )


VARIABLE_RULES = [
    UnusedAnnotation,
    UnusedIndirectAssignment,
]

__all__ = [
    "VARIABLE_RULES",
    "UnusedAnnotation",
    "UnusedIndirectAssignment",
]
