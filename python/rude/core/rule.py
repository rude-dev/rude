"""
Base Rule class for Rude linter.

Simple API for rule authors with support for node filtering,
configuration, and metadata dependencies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, ClassVar

from rude.core.node_types import NodeType

if TYPE_CHECKING:
    from rude._rust import LineInfo
    from rude.core.node import Node
    from rude.core.types import Diagnostic, FileContext, Fix, Severity


class RuleBase:
    """Shared base for all rule types (Rule, LineRule)."""

    code: ClassVar[str]
    """Unique rule code (e.g., 'S001', 'ACME001')."""

    message: ClassVar[str]
    """Default diagnostic message."""

    severity: ClassVar[Severity | None] = None
    """Default severity. None = ERROR."""

    def configure(self, options: dict[str, Any]) -> None:
        """Configure rule from [tool.rude.rules.XXXX]."""
        pass

    def should_check_file(self, ctx: FileContext) -> bool:
        """Return False to skip this file."""
        return True

    def diagnostic_at(
        self,
        line: int,
        column: int,
        message: str | None = None,
        *,
        fix: Fix | None = None,
        severity: Severity | None = None,
    ) -> Diagnostic:
        """Create a diagnostic at a specific location."""
        from rude.core.types import Diagnostic, Location, Severity

        return Diagnostic(
            code=self.code,
            message=message or self.message,
            location=Location(line=line, column=column),
            severity=severity or self.severity or Severity.ERROR,
            fix=fix,
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} ({self.code})>"


class Rule(RuleBase, ABC):
    """
    Base class for linting rules.

    Example::

        class NoEval(Rule):
            code = "S001"
            message = "eval() is a security risk"
            node_types = {NodeType.CALL}

            def check(self, node: Node) -> Iterator[Diagnostic]:
                if node.function_name == "eval":
                    yield self.diagnostic(node)
    """

    node_types: ClassVar[set[NodeType] | None] = None
    """Tree-sitter node types to match. None = all nodes (discouraged)."""

    metadata_dependencies: ClassVar[set[type]] = set()
    """Required metadata providers."""

    @abstractmethod
    def check(self, node: Node) -> Iterator[Diagnostic]:
        """Check a node and yield diagnostics."""
        ...

    def diagnostic(
        self,
        node: Node,
        message: str | None = None,
        *,
        fix: Fix | None = None,
        severity: Severity | None = None,
    ) -> Diagnostic:
        """Create a diagnostic for this rule."""
        from rude.core.types import Diagnostic, Severity

        return Diagnostic(
            code=self.code,
            message=message or self.message,
            location=node.location,
            severity=severity or self.severity or Severity.ERROR,
            fix=fix,
        )


class LineRule(RuleBase, ABC):
    """
    Base class for line-based rules.

    More efficient than AST rules for pattern matching on raw text.
    The linter iterates lines once and calls all LineRules, avoiding
    redundant iteration.

    Example::

        class NoTodoComments(LineRule):
            code = "TODO001"
            message = "TODO comment found"

            def check_line(self, line: str, lineno: int, ctx: FileContext) -> Iterator[Diagnostic]:
                if "TODO" in line:
                    col = line.index("TODO")
                    yield self.diagnostic_at(lineno, col)
    """

    uses_line_infos: ClassVar[bool] = False
    """If True, check_line_info is used when pre-computed line metadata
    is available (from Rust), avoiding per-line decode and regex."""

    @abstractmethod
    def check_line(
        self,
        line: str,
        lineno: int,
        ctx: FileContext,
        *,
        comment_pos: int = -1,
    ) -> Iterator[Diagnostic]:
        """
        Check a single line and yield diagnostics.

        Args:
            line: The line content (decoded string, no trailing newline)
            lineno: Line number (1-based)
            ctx: File context for accessing file-level info
            comment_pos: Position of '#' comment start (-1 if none).
                Pre-computed by linter, ignores '#' inside strings.
                Use `line[:comment_pos]` to get code portion.

        Yields:
            Diagnostic objects for any issues found
        """
        ...

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        """
        Fast path using pre-computed line metadata from Rust.

        Override this when ``uses_line_infos = True``. The ``info`` argument
        is a ``LineInfo`` struct (frozen pyclass) with named fields::

            info.leading_spaces     (int)
            info.indent_len         (int)
            info.line_len           (int)
            info.trailing_ws        (int)
            info.comment_start      (int, -1 if no comment)
            info.indent_has_tab     (bool)
            info.indent_has_space   (bool)
            info.is_blank           (bool)
            info.is_in_string       (bool)
            info.spaces_before_comment (int, -1 for block comment)
            info.char_after_hash    (int, ASCII byte or 0)
            info.leading_hashes     (int)
            info.style_flags        (int, bitfield)

        style_flags is a u8 bitfield with optimization hints::

            bit 0 (0x01): DOUBLE_SPACE_AROUND_OP  -- 2+ spaces near operator
            bit 1 (0x02): TAB_AROUND_OP           -- tab near operator
            bit 2 (0x04): DOUBLE_SPACE_AFTER_COMMA -- 2+ spaces after , or ;
            bit 3 (0x08): TAB_AFTER_COMMA         -- tab after , or ;
            bit 4 (0x10): DOUBLE_SPACE_AROUND_KW  -- 2+ spaces near keyword
            bit 5 (0x20): TAB_AROUND_KW           -- tab near keyword

        Flags are hints: false positives OK, false negatives not allowed.
        """
        return iter(())


__all__ = ["LineRule", "Rule"]
