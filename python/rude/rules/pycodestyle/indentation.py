"""
Indentation rules: E1xx, W191.

E101: indentation contains mixed spaces and tabs
E111: indentation is not a multiple of four
E117: over-indented
W191: indentation contains tabs
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import LineRule, Rule
from rude.core.types import Diagnostic, FileContext, Severity

if TYPE_CHECKING:
    from rude._rust import LineInfo
    from rude.core.node import Node


class IndentationContainsMixedSpacesAndTabs(LineRule):
    """
    E101: Indentation contains mixed spaces and tabs.

    Rationale: Mixing tabs and spaces makes indentation ambiguous and
    can cause ``TabError`` in Python 3.

    Example::

        def foo():
        \t x = 1     # E101 - tab after spaces

        def foo():
            x = 1    # OK - spaces only
    """

    code: ClassVar[str] = "E101"
    message: ClassVar[str] = "indentation contains mixed spaces and tabs"
    uses_line_infos: ClassVar[bool] = True

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        # Get leading whitespace
        match = re.match(r"^([ \t]+)", line)
        if match:
            indent = match.group(1)
            has_spaces = " " in indent
            has_tabs = "\t" in indent
            if has_spaces and has_tabs:
                yield self.diagnostic_at(lineno, 0)

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        if info.indent_has_tab and info.indent_has_space:
            yield self.diagnostic_at(lineno, 0)


class IndentationNotMultipleOfFour(LineRule):
    """
    E111: Indentation is not a multiple of the configured indent size.

    Rationale: PEP 8 recommends 4-space indentation. Inconsistent
    indentation reduces readability.

    Example::

        if True:
           x = 1     # E111 - 3 spaces, not 4

        if True:
            x = 1    # OK - 4 spaces

    Configuration:
        [tool.rude.rules.E111]
        indent_size = 4  # default
    """

    code: ClassVar[str] = "E111"
    message: ClassVar[str] = "indentation is not a multiple of {indent_size}"
    uses_line_infos: ClassVar[bool] = True

    indent_size: int = 4

    def configure(self, options: dict[str, Any]) -> None:
        self.indent_size = options.get("indent_size", 4)

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        # Skip empty lines and comments
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            return

        # Skip lines inside multi-line strings (docstrings, SQL, etc.)
        if lineno in ctx.string_lines:
            return

        # Count leading spaces (ignore tabs for this rule)
        match = re.match(r"^( +)", line)
        if match:
            spaces = len(match.group(1))
            if spaces % self.indent_size != 0:
                yield self.diagnostic_at(
                    lineno, 0, self.message.format(indent_size=self.indent_size)
                )

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        leading_spaces, indent_len = info.leading_spaces, info.indent_len
        comment_start = info.comment_start
        is_blank, is_in_string = info.is_blank, info.is_in_string
        if is_blank or is_in_string:
            return
        # Skip comment-only lines: # immediately after indent
        if comment_start == indent_len:
            return
        if leading_spaces > 0 and leading_spaces % self.indent_size != 0:
            yield self.diagnostic_at(lineno, 0, self.message.format(indent_size=self.indent_size))


class OverIndented(Rule):
    """
    E117: Over-indented.

    Rationale: Over-indentation misrepresents the logical structure
    and reduces readability.

    Example::

        if True:
                x = 1     # E117 - too many spaces

        if True:
            x = 1         # OK
    """

    code: ClassVar[str] = "E117"
    message: ClassVar[str] = "over-indented"
    node_types = {NodeType.BLOCK}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Check first statement in block
        if not node.named_children:
            return

        first_child = node.named_children[0]
        parent = node.parent
        if not parent:
            return

        # Expected indent is parent indent + 4
        parent_indent = parent.column
        expected_indent = parent_indent + 4
        actual_indent = first_child.column

        # Allow some flexibility, but flag obvious over-indentation
        if actual_indent > expected_indent + 4:
            yield self.diagnostic_at(first_child.line, actual_indent)


class IndentationContainsTabs(LineRule):
    """
    W191: Indentation contains tabs.

    Rationale: PEP 8 requires spaces for indentation. Tabs render
    inconsistently across editors.

    Example::

        def foo():
        \tx = 1     # W191 - tab used for indentation

        def foo():
            x = 1   # OK - spaces only
    """

    code: ClassVar[str] = "W191"
    message: ClassVar[str] = "indentation contains tabs"
    severity: ClassVar[Severity] = Severity.WARNING
    uses_line_infos: ClassVar[bool] = True

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        # Check if line starts with tab or has tabs in leading whitespace
        if line.startswith("\t") or re.match(r"^[ ]*\t", line):
            yield self.diagnostic_at(lineno, 0)

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        if info.indent_has_tab:
            yield self.diagnostic_at(lineno, 0)


INDENTATION_RULES = [
    IndentationContainsMixedSpacesAndTabs,
    IndentationNotMultipleOfFour,
    OverIndented,
    IndentationContainsTabs,
]

__all__ = [
    "INDENTATION_RULES",
    "IndentationContainsMixedSpacesAndTabs",
    "IndentationContainsTabs",
    "IndentationNotMultipleOfFour",
    "OverIndented",
]
