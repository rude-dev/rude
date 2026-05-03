"""
Warning rules: W291-W293, W391, W605.

W291: trailing whitespace
W292: no newline at end of file
W293: blank line contains whitespace
W391: blank line at end of file
W605: invalid escape sequence
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import LineRule, Rule
from rude.core.types import Diagnostic, Edit, FileContext, Fix

if TYPE_CHECKING:
    from rude._rust import LineInfo
    from rude.core.node import Node


class TrailingWhitespace(LineRule):
    """
    W291: Trailing whitespace.

    Rationale: Trailing whitespace creates noisy diffs and is banned
    by PEP 8.

    Example::

        x = 1   \\n    # W291 - trailing spaces

        x = 1\\n       # OK
    """

    code: ClassVar[str] = "W291"
    message: ClassVar[str] = "trailing whitespace"
    uses_line_infos: ClassVar[bool] = True

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        # Check for trailing whitespace (but not blank lines - that's W293)
        if line and line != line.rstrip():
            yield self.diagnostic_at(
                lineno,
                len(line.rstrip()),
                fix=self._make_fix(lineno, line, ctx),
            )

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        line_len = info.line_len
        trailing_ws = info.trailing_ws
        if line_len > 0 and trailing_ws > 0:
            col = line_len - trailing_ws
            yield self.diagnostic_at(
                lineno,
                col,
                fix=self._make_fix_from_info(lineno, line_len, trailing_ws, ctx),
            )

    def _make_fix(self, lineno: int, line: str, ctx: FileContext) -> Fix:
        """Create fix to remove trailing whitespace."""
        line_start = ctx.line_start_byte(lineno)
        old_end = line_start + len(line)
        new_end = line_start + len(line.rstrip())
        return Fix(
            description="Remove trailing whitespace",
            edits=(Edit(new_end, old_end, ""),),
        )

    def _make_fix_from_info(
        self,
        lineno: int,
        line_len: int,
        trailing_ws: int,
        ctx: FileContext,
    ) -> Fix:
        """Create fix using pre-computed line info (no decode needed)."""
        line_start = ctx.line_start_byte(lineno)
        old_end = line_start + line_len
        new_end = old_end - trailing_ws
        return Fix(
            description="Remove trailing whitespace",
            edits=(Edit(new_end, old_end, ""),),
        )


class NoNewlineAtEndOfFile(Rule):
    """
    W292: No newline at end of file.

    Rationale: POSIX requires text files to end with a newline.
    Missing newlines cause issues with some tools and diffs.

    Example::

        x = 1<EOF>      # W292 - missing final newline

        x = 1\\n<EOF>   # OK
    """

    code: ClassVar[str] = "W292"
    message: ClassVar[str] = "no newline at end of file"
    node_types = {NodeType.MODULE}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if node.parent is not None:
            return

        ctx = node.ctx
        if not ctx.source:
            return

        # Check if file ends with newline
        if not ctx.source.endswith(b"\n"):
            last_line = len(ctx.lines)
            last_col = len(ctx.lines[-1]) if ctx.lines else 0
            yield self.diagnostic_at(
                last_line,
                last_col,
                fix=Fix(
                    description="Add newline at end of file",
                    edits=(Edit(len(ctx.source), len(ctx.source), "\n"),),
                ),
            )


class BlankLineContainsWhitespace(LineRule):
    """
    W293: Blank line contains whitespace.

    Rationale: Invisible whitespace on blank lines creates noisy diffs
    and wastes bytes.

    Example::

        x = 1
            \\n        # W293 - blank line with spaces
        y = 2

        x = 1
        \\n            # OK - truly blank
        y = 2
    """

    code: ClassVar[str] = "W293"
    message: ClassVar[str] = "blank line contains whitespace"
    uses_line_infos: ClassVar[bool] = True

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        # Blank line with whitespace (line is already stripped of newlines)
        if line and line.isspace():
            yield self.diagnostic_at(
                lineno,
                0,
                fix=self._make_fix(lineno, line, ctx),
            )

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        line_len = info.line_len
        is_blank = info.is_blank
        if is_blank and line_len > 0:
            yield self.diagnostic_at(
                lineno,
                0,
                fix=self._make_fix_from_info(lineno, line_len, ctx),
            )

    def _make_fix(self, lineno: int, line: str, ctx: FileContext) -> Fix:
        """Create fix to remove whitespace from blank line."""
        line_start = ctx.line_start_byte(lineno)
        return Fix(
            description="Remove whitespace from blank line",
            edits=(Edit(line_start, line_start + len(line), ""),),
        )

    def _make_fix_from_info(self, lineno: int, line_len: int, ctx: FileContext) -> Fix:
        """Create fix using pre-computed line info (no decode needed)."""
        line_start = ctx.line_start_byte(lineno)
        return Fix(
            description="Remove whitespace from blank line",
            edits=(Edit(line_start, line_start + line_len, ""),),
        )


class BlankLineAtEndOfFile(Rule):
    """
    W391: Blank line at end of file.

    Rationale: Trailing blank lines add no value and create noisy
    diffs.

    Example::

        x = 1
        \\n<EOF>       # W391 - trailing blank line

        x = 1\\n<EOF>  # OK
    """

    code: ClassVar[str] = "W391"
    message: ClassVar[str] = "blank line at end of file"
    node_types = {NodeType.MODULE}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if node.parent is not None:
            return

        ctx = node.ctx
        lines = ctx.lines

        if len(lines) < 2:
            return

        # Check for blank lines at end
        blank_count = 0
        for line in reversed(lines):
            stripped = line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not stripped:
                blank_count += 1
            else:
                break

        if blank_count > 0:
            # Report on first blank line at end
            yield self.diagnostic_at(len(lines) - blank_count + 1, 0)


class InvalidEscapeSequence(Rule):
    """
    W605: Invalid escape sequence.

    Rationale: Invalid escape sequences raise ``DeprecationWarning``
    in Python 3.12+ and will become ``SyntaxError`` in a future version.

    Example::

        x = "\\d+"      # W605 - invalid escape sequence

        x = r"\\d+"     # OK - raw string
        x = "\\\\d+"    # OK - escaped backslash
    """

    code: ClassVar[str] = "W605"
    message: ClassVar[str] = "invalid escape sequence '\\{char}'"
    node_types = {NodeType.STRING}

    # Valid escape sequences in Python
    VALID_ESCAPES = set("\\abfnrtvx01234567NuU'\"")

    def check(self, node: Node) -> Iterator[Diagnostic]:
        text = node.text

        # Skip raw strings
        if text.startswith(
            (
                "r'",
                'r"',
                "R'",
                'R"',
                "br'",
                'br"',
                "Br'",
                'Br"',
                "bR'",
                'bR"',
                "BR'",
                'BR"',
                "rb'",
                'rb"',
                "rB'",
                'rB"',
                "Rb'",
                'Rb"',
                "RB'",
                'RB"',
            )
        ):
            return

        # Skip f-strings that are also raw
        if text.startswith(
            (
                "fr'",
                'fr"',
                "Fr'",
                'Fr"',
                "fR'",
                'fR"',
                "FR'",
                'FR"',
                "rf'",
                'rf"',
                "rF'",
                'rF"',
                "Rf'",
                'Rf"',
                "RF'",
                'RF"',
            )
        ):
            return

        # Find string content (after quotes)
        quote_char = None
        triple_quote = False
        start_idx = 0

        for i, c in enumerate(text):
            if c in ('"', "'"):
                quote_char = c
                if text[i : i + 3] == c * 3:
                    triple_quote = True
                    start_idx = i + 3
                else:
                    start_idx = i + 1
                break

        if quote_char is None:
            return

        end_idx = len(text) - (3 if triple_quote else 1)
        content = text[start_idx:end_idx]

        # Find invalid escape sequences
        i = 0
        while i < len(content):
            if content[i] == "\\":
                if i + 1 < len(content):
                    next_char = content[i + 1]
                    if next_char not in self.VALID_ESCAPES and next_char != "\n":
                        # Calculate position in original source
                        # This is approximate - good enough for most cases
                        yield self.diagnostic(
                            node,
                            self.message.format(char=next_char),
                        )
                        # Only report first invalid escape per string
                        return
                i += 2
            else:
                i += 1


WARNING_RULES = [
    TrailingWhitespace,
    NoNewlineAtEndOfFile,
    BlankLineContainsWhitespace,
    BlankLineAtEndOfFile,
    InvalidEscapeSequence,
]

__all__ = [
    "WARNING_RULES",
    "BlankLineAtEndOfFile",
    "BlankLineContainsWhitespace",
    "InvalidEscapeSequence",
    "NoNewlineAtEndOfFile",
    "TrailingWhitespace",
]
