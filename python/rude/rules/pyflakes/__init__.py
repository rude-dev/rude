"""
Pyflakes-style rules ported to Rude.

F401: Module imported but unused
F541: f-string without any placeholders
F542: t-string without any placeholders
F601: Dictionary key literal repeated
F602: Dictionary key variable repeated
F621: Too many expressions in star-unpacking
F622: Two starred expressions in assignment
F631: Assert test is non-empty tuple
F632: Use of is/is not with literal
F634: If test is non-empty tuple
F701: break outside loop
F702: continue outside loop
F704: yield outside function
F706: return outside function
F707: default except not last
F824: global/nonlocal declared but never assigned
F831: Duplicate argument in function definition
F841: Local variable assigned but never used
F901: raise NotImplemented (should be NotImplementedError)

These rules use tree-sitter for AST analysis and ScopeProvider for
accurate scope tracking.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Edit, Fix, Location, Severity
from rude.providers import ScopeProvider
from rude.rules.pyflakes.annotations import (
    ANNOTATION_RULES,
    ForwardAnnotationSyntaxError,
)

# Import rules from submodules
from rude.rules.pyflakes.control_flow import (
    CONTROL_FLOW_RULES,
    BreakOutsideLoop,
    ContinueOutsideLoop,
    DefaultExceptNotLast,
    ReturnOutsideFunction,
    YieldOutsideFunction,
)
from rude.rules.pyflakes.docstrings import (
    DOCSTRING_RULES,
    DoctestSyntaxError,
)
from rude.rules.pyflakes.format_strings import (
    FORMAT_STRING_RULES,
    PercentFormatExpectedMapping,
    PercentFormatExpectedSequence,
    PercentFormatExtraNamedArguments,
    PercentFormatInvalidFormat,
    PercentFormatMissingArgument,
    PercentFormatMixedPositionalAndNamed,
    PercentFormatPositionalCountMismatch,
    PercentFormatStarRequiresSequence,
    PercentFormatUnsupportedCharacter,
    StringDotFormatExtraNamedArguments,
    StringDotFormatExtraPositionalArguments,
    StringDotFormatInvalidFormat,
    StringDotFormatMissingArgument,
    StringDotFormatMixingAutomatic,
)
from rude.rules.pyflakes.imports import (
    IMPORT_RULES,
    FutureFeatureNotDefined,
    ImportShadowedByLoopVar,
    ImportStarNotPermitted,
    ImportStarUsed,
    LateFutureImport,
    RedefinedWhileUnused,
)
from rude.rules.pyflakes.literals import (
    LITERAL_RULES,
    FStringMissingPlaceholders,
    TStringMissingPlaceholders,
)
from rude.rules.pyflakes.names import (
    NAME_RULES,
    UndefinedExport,
    UndefinedLocal,
    UndefinedName,
)
from rude.rules.pyflakes.syntax import (
    SYNTAX_RULES,
    AssertTuple,
    DuplicateArgument,
    IfTuple,
    InvalidPrintSyntax,
    IsLiteral,
    MultiValueRepeatedKeyLiteral,
    MultiValueRepeatedKeyVariable,
    RaiseNotImplemented,
    TooManyExpressionsInStarredAssignment,
    TwoStarredExpressions,
)
from rude.rules.pyflakes.variables import (
    VARIABLE_RULES,
    UnusedAnnotation,
    UnusedIndirectAssignment,
)

if TYPE_CHECKING:
    from rude.core.node import Node


class UnusedVariable(Rule):
    """
    F841: Local variable is assigned but never used.

    Ported from flake8/pyflakes.

    Example::

        def foo():
            x = 1      # F841 - x is never used
            y = 2
            return y

    Configuration::

        [tool.rude.rules.F841]
        ignore_prefixes = ["_", "unused_"]

    Optimized: Uses pre-computed unused_variables from Rust SemanticModel.
    """

    code: ClassVar[str] = "F841"
    message: ClassVar[str] = "Local variable '{name}' is assigned but never used"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.MODULE}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    # Config
    ignore_prefixes: tuple[str, ...] = ("_",)

    def configure(self, options: dict[str, Any]) -> None:
        if "ignore_prefixes" in options:
            self.ignore_prefixes = tuple(options["ignore_prefixes"])

    def check(self, node: Node) -> Iterator[Diagnostic]:
        """Check for unused variables using pre-computed list from Rust."""
        scope_prov: ScopeProvider = node.ctx.get_metadata(ScopeProvider)
        model = scope_prov.model

        # Iterate over pre-computed unused variables
        for entry in model.unused_variables:
            name = entry.name
            # Skip ignored prefixes (already filtered by Rust for "_")
            if len(self.ignore_prefixes) > 1 and any(
                name.startswith(p) for p in self.ignore_prefixes if p != "_"
            ):
                continue

            # Create fix
            fix = Fix(
                description=f"Rename to `_{name}`",
                edits=(Edit(entry.start_byte, entry.end_byte, f"_{name}"),),
            )
            yield Diagnostic(
                code=self.code,
                message=self.message.format(name=name),
                location=Location(line=entry.line, column=entry.column),
                severity=self.severity,
                fix=fix,
            )


class UnusedImport(Rule):
    """
    F401: Module imported but unused.

    Example::

        import os      # F401 - os is never used
        import sys
        print(sys.version)

    Optimized: Uses pre-computed unused_imports from Rust SemanticModel.
    """

    code: ClassVar[str] = "F401"
    message: ClassVar[str] = "'{name}' imported but unused"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.MODULE}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        """Check for unused imports using pre-computed list from Rust."""
        scope_prov: ScopeProvider = node.ctx.get_metadata(ScopeProvider)
        model = scope_prov.model

        # Iterate over pre-computed unused imports
        for entry in model.unused_imports:
            yield Diagnostic(
                code=self.code,
                message=self.message.format(name=entry.name),
                location=Location(line=entry.line, column=entry.column),
                severity=self.severity,
            )


# Collect all pyflakes rules
PYFLAKES_RULES = [
    UnusedVariable,
    UnusedImport,
    *CONTROL_FLOW_RULES,
    *SYNTAX_RULES,
    *LITERAL_RULES,
    *NAME_RULES,
    *IMPORT_RULES,
    *VARIABLE_RULES,
    *FORMAT_STRING_RULES,
    *ANNOTATION_RULES,
    *DOCSTRING_RULES,
]

__all__ = [
    # All rules
    "PYFLAKES_RULES",
    "AssertTuple",
    "BreakOutsideLoop",
    "ContinueOutsideLoop",
    "DefaultExceptNotLast",
    # Docstring rules
    "DoctestSyntaxError",
    "DuplicateArgument",
    # Literal rules
    "FStringMissingPlaceholders",
    # Annotation rules
    "ForwardAnnotationSyntaxError",
    "FutureFeatureNotDefined",
    "IfTuple",
    # Import rules
    "ImportShadowedByLoopVar",
    "ImportStarNotPermitted",
    "ImportStarUsed",
    "InvalidPrintSyntax",
    "IsLiteral",
    "LateFutureImport",
    "MultiValueRepeatedKeyLiteral",
    "MultiValueRepeatedKeyVariable",
    "PercentFormatExpectedMapping",
    "PercentFormatExpectedSequence",
    "PercentFormatExtraNamedArguments",
    "PercentFormatInvalidFormat",
    "PercentFormatMissingArgument",
    "PercentFormatMixedPositionalAndNamed",
    "PercentFormatPositionalCountMismatch",
    "PercentFormatStarRequiresSequence",
    "PercentFormatUnsupportedCharacter",
    "RaiseNotImplemented",
    "RedefinedWhileUnused",
    # Control flow rules
    "ReturnOutsideFunction",
    "StringDotFormatExtraNamedArguments",
    "StringDotFormatExtraPositionalArguments",
    # Format string rules
    "StringDotFormatInvalidFormat",
    "StringDotFormatMissingArgument",
    "StringDotFormatMixingAutomatic",
    "TStringMissingPlaceholders",
    # Syntax rules
    "TooManyExpressionsInStarredAssignment",
    "TwoStarredExpressions",
    "UndefinedExport",
    "UndefinedLocal",
    # Name rules
    "UndefinedName",
    # Variable rules
    "UnusedAnnotation",
    "UnusedImport",
    "UnusedIndirectAssignment",
    # Original rules
    "UnusedVariable",
    "YieldOutsideFunction",
]
