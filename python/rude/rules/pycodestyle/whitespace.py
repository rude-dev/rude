"""
Whitespace rules: E2xx.

E201: whitespace after '('
E202: whitespace before ')'
E203: whitespace before ':'
E211: whitespace before '(' (function call)
E221: multiple spaces before operator
E222: multiple spaces after operator
E223: tab before operator
E224: tab after operator
E225: missing whitespace around operator
E226: missing whitespace around arithmetic operator (ignored by default)
E227: missing whitespace around bitwise operator
E228: missing whitespace around modulo operator
E231: missing whitespace after ','
E241: multiple spaces after ',' (ignored by default)
E242: tab after ',' (ignored by default)
E251: unexpected spaces around keyword / parameter equals
E261: at least two spaces before inline comment
E262: inline comment should start with '# '
E265: block comment should start with '# '
E266: too many leading '#' for block comment
E271: multiple spaces after keyword
E272: multiple spaces before keyword
E273: tab after keyword
E274: tab before keyword
E275: missing whitespace after keyword
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import LineRule, Rule
from rude.core.types import Diagnostic, Edit, FileContext, Fix, Location, Severity

if TYPE_CHECKING:
    from rude._rust import LineInfo
    from rude.core.node import Node

# style_flags bit constants (LineInfo.style_flags field)
_DOUBLE_SPACE_AROUND_OP = 0x01  # E221, E222
_TAB_AROUND_OP = 0x02  # E223, E224
_DOUBLE_SPACE_AFTER_COMMA = 0x04  # E241
_TAB_AFTER_COMMA = 0x08  # E242
_DOUBLE_SPACE_AROUND_KW = 0x10  # E271, E272
_TAB_AROUND_KW = 0x20  # E273, E274


class WhitespaceAfterOpenBracket(Rule):
    """
    E201: Whitespace after '(', '[', or '{'.

    Rationale: PEP 8 requires no whitespace immediately after opening
    brackets.

    Example::

        spam( ham)      # E201
        spam(ham)       # OK
    """

    code: ClassVar[str] = "E201"
    message: ClassVar[str] = "whitespace after '{bracket}'"
    node_types = {
        NodeType.ARGUMENT_LIST,
        NodeType.PARAMETERS,
        NodeType.TUPLE,
        NodeType.LIST,
        NodeType.DICTIONARY,
        NodeType.SET,
        NodeType.SUBSCRIPT,
    }

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Quick-reject: empty brackets can't have whitespace issues
        if node.named_child_count == 0:
            return
        children = node.children
        if not children:
            return

        for i, child in enumerate(children):
            if child.type in ("(", "[", "{") and i + 1 < len(children):
                next_child = children[i + 1]
                # Same line, space after bracket; check it's not empty brackets
                if (
                    next_child.line == child.line
                    and next_child.column > child.column + 1
                    and next_child.type not in (")", "]", "}")
                ):
                    yield self.diagnostic_at(
                        child.line,
                        child.column + 1,
                        self.message.format(bracket=child.text),
                    )


class WhitespaceBeforeCloseBracket(Rule):
    """
    E202: Whitespace before ')', ']', or '}'.

    Rationale: PEP 8 requires no whitespace immediately before closing
    brackets.

    Example::

        spam(ham )      # E202
        spam(ham)       # OK
    """

    code: ClassVar[str] = "E202"
    message: ClassVar[str] = "whitespace before '{bracket}'"
    node_types = {
        NodeType.ARGUMENT_LIST,
        NodeType.PARAMETERS,
        NodeType.TUPLE,
        NodeType.LIST,
        NodeType.DICTIONARY,
        NodeType.SET,
        NodeType.SUBSCRIPT,
    }

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Quick-reject: empty brackets can't have whitespace issues
        if node.named_child_count == 0:
            return
        children = node.children
        if not children:
            return

        for i, child in enumerate(children):
            if child.type in (")", "]", "}") and i > 0:
                prev_child = children[i - 1]
                expected_col = prev_child.end_column
                # Same line, space before bracket; check it's not empty brackets
                if (
                    prev_child.line == child.line
                    and child.column > expected_col
                    and prev_child.type not in ("(", "[", "{")
                ):
                    yield self.diagnostic_at(
                        child.line,
                        expected_col,
                        self.message.format(bracket=child.text),
                    )


class WhitespaceBeforeColon(Rule):
    """
    E203: Whitespace before ':' or ','.

    Rationale: PEP 8 requires no whitespace immediately before colons,
    commas, or semicolons.

    Example::

        spam[1 :]       # E203
        spam[1:]        # OK
    """

    code: ClassVar[str] = "E203"
    message: ClassVar[str] = "whitespace before '{char}'"
    node_types = {
        NodeType.SLICE,
        NodeType.PAIR,
        NodeType.DICTIONARY,
        NodeType.ARGUMENT_LIST,
        NodeType.PARAMETERS,
    }

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if node.named_child_count == 0:
            return
        for child in node.children:
            if child.type in (":", ","):
                prev = child.prev_sibling
                if prev and prev.line == child.line:
                    expected = prev.end_column
                    if child.column > expected:
                        yield self.diagnostic_at(
                            child.line, expected, self.message.format(char=child.text)
                        )


class WhitespaceBeforeParameters(Rule):
    """
    E211: Whitespace before '(' in function call.

    Rationale: PEP 8 requires no whitespace between a function name
    and its argument list.

    Example::

        spam (1)        # E211
        spam(1)         # OK
    """

    code: ClassVar[str] = "E211"
    message: ClassVar[str] = "whitespace before '('"
    node_types = {NodeType.CALL}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        func = node.child_by_field("function")
        args = node.child_by_field("arguments")

        if func and args and args.line == func.end_line and args.column > func.end_column:
            # Check if there's space between function and arguments
            yield self.diagnostic_at(func.end_line, func.end_column)


class MissingWhitespaceAfterComma(Rule):
    """
    E231: Missing whitespace after ',', ';', or ':'.

    Rationale: PEP 8 requires a space after commas, semicolons, and
    colons for readability.

    Example::

        [1,2,3]         # E231 (multiple)
        [1, 2, 3]       # OK
    """

    code: ClassVar[str] = "E231"
    message: ClassVar[str] = "missing whitespace after '{char}'"
    node_types = {
        NodeType.ARGUMENT_LIST,
        NodeType.PARAMETERS,
        NodeType.TUPLE,
        NodeType.LIST,
        NodeType.DICTIONARY,
        NodeType.PAIR,
    }

    def check(self, node: Node) -> Iterator[Diagnostic]:
        for child in node.children:
            if child.type == ",":
                next_sib = child.next_sibling
                if (
                    next_sib
                    and next_sib.line == child.line
                    and next_sib.column == child.column + 1
                    and next_sib.type not in (")", "]", "}")
                ):
                    # Next token should start at column + 2 (comma + space)
                    yield self.diagnostic_at(
                        child.line, child.column + 1, self.message.format(char=",")
                    )


class UnexpectedSpacesAroundKeywordEquals(Rule):
    """
    E251: Unexpected spaces around keyword / parameter equals.

    Rationale: PEP 8 requires no spaces around ``=`` in default
    parameter values and keyword arguments.

    Example::

        def foo(x = 1):     # E251
        def foo(x=1):       # OK
    """

    code: ClassVar[str] = "E251"
    message: ClassVar[str] = "unexpected spaces around keyword / parameter equals"
    node_types = {NodeType.DEFAULT_PARAMETER, NodeType.KEYWORD_ARGUMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        for child in node.children:
            if child.type == "=":
                prev = child.prev_sibling
                next_sib = child.next_sibling

                has_space_before = (
                    prev and prev.line == child.line and child.column > prev.end_column
                )
                has_space_after = (
                    next_sib and next_sib.line == child.line and next_sib.column > child.column + 1
                )

                if has_space_before or has_space_after:
                    yield self.diagnostic(child)


# ─────────────────────────────────────────────────────────────────────────────
# E261-E266: Comment whitespace (optimized with LineRule)
# ─────────────────────────────────────────────────────────────────────────────


def _is_inline_comment(line: str, comment_pos: int) -> bool:
    """Check if the comment is inline (has code before it)."""
    before = line[:comment_pos]
    return bool(before.strip())


class TwoSpacesBeforeInlineComment(LineRule):
    """
    E261: At least two spaces before inline comment.

    Rationale: PEP 8 requires at least two spaces before an inline
    comment to visually separate code from comments.

    Example::

        x = 1 # comment     # E261
        x = 1  # comment    # OK
    """

    code: ClassVar[str] = "E261"
    message: ClassVar[str] = "at least two spaces before inline comment"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        spaces_before_comment = info.spaces_before_comment
        if spaces_before_comment < 0:
            return  # not inline or no comment
        if spaces_before_comment < 2:
            comment_start = info.comment_start
            yield self.diagnostic_at(
                lineno,
                comment_start,
                fix=self._make_fix(lineno, comment_start, spaces_before_comment, ctx),
            )

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        if comment_pos <= 0:
            return
        if not _is_inline_comment(line, comment_pos):
            return
        before = line[:comment_pos]
        spaces = len(before) - len(before.rstrip())
        if spaces < 2:
            yield self.diagnostic_at(
                lineno,
                comment_pos,
                fix=self._make_fix(lineno, comment_pos, spaces, ctx),
            )

    def _make_fix(self, lineno: int, comment_pos: int, cur_spaces: int, ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        start = line_start + comment_pos - cur_spaces
        end = line_start + comment_pos
        return Fix(description="Set two spaces before comment", edits=(Edit(start, end, "  "),))


class InlineCommentShouldStartWithSpace(LineRule):
    """
    E262: Inline comment should start with '# '.

    Rationale: PEP 8 requires a space after ``#`` in comments for
    readability.

    Example::

        x = 1  #comment     # E262
        x = 1  # comment    # OK
    """

    code: ClassVar[str] = "E262"
    message: ClassVar[str] = "inline comment should start with '# '"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        spaces_before_comment = info.spaces_before_comment
        if spaces_before_comment < 0:
            return  # not inline
        char_after_hash = info.char_after_hash
        if char_after_hash == 0:
            return  # just "#"
        if char_after_hash in (ord(" "), ord("#"), ord("!"), ord(":")):
            return
        comment_start = info.comment_start
        yield self.diagnostic_at(
            lineno,
            comment_start,
            fix=self._make_fix(lineno, comment_start, ctx),
        )

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        if comment_pos < 0:
            return
        if not _is_inline_comment(line, comment_pos):
            return
        comment = line[comment_pos:]
        if len(comment) > 1:
            after_hash = comment[1:]
            if after_hash.strip() and not after_hash.startswith((" ", "#", "!", ":")):
                yield self.diagnostic_at(
                    lineno,
                    comment_pos,
                    fix=self._make_fix(lineno, comment_pos, ctx),
                )

    def _make_fix(self, lineno: int, comment_pos: int, ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        pos = line_start + comment_pos + 1  # After the #
        return Fix(description="Add space after #", edits=(Edit(pos, pos, " "),))


class BlockCommentShouldStartWithSpace(LineRule):
    """
    E265: Block comment should start with '# '.

    Rationale: PEP 8 requires a space after ``#`` in block comments
    for readability.

    Example::

        #comment            # E265
        # comment           # OK
        #: Sphinx docstring # OK
        #                   # OK (empty comment)
    """

    code: ClassVar[str] = "E265"
    message: ClassVar[str] = "block comment should start with '# '"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        spaces_before_comment = info.spaces_before_comment
        if spaces_before_comment >= 0:
            return  # inline comment, E262 handles those
        comment_start = info.comment_start
        if comment_start < 0:
            return  # no comment
        leading_hashes = info.leading_hashes
        if leading_hashes != 1:
            return  # E266 handles multiple hashes
        char_after_hash = info.char_after_hash
        if char_after_hash == 0:
            return  # just "#"
        if char_after_hash in (ord(" "), ord("#"), ord("!"), ord(":")):
            return
        yield self.diagnostic_at(
            lineno,
            comment_start,
            fix=self._make_fix(lineno, comment_start, ctx),
        )

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        if comment_pos < 0:
            return
        if _is_inline_comment(line, comment_pos):
            return
        comment = line[comment_pos:]
        if len(comment) > 1:
            after_hash = comment[1:]
            if after_hash.strip() and not after_hash.startswith((" ", "#", "!", ":")):
                yield self.diagnostic_at(
                    lineno,
                    comment_pos,
                    fix=self._make_fix(lineno, comment_pos, ctx),
                )

    def _make_fix(self, lineno: int, comment_pos: int, ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        pos = line_start + comment_pos + 1
        return Fix(description="Add space after #", edits=(Edit(pos, pos, " "),))


class TooManyHashesForBlockComment(LineRule):
    """
    E266: Too many leading '#' for block comment.

    Rationale: PEP 8 requires block comments to start with a single
    ``#`` followed by a space.

    Example::

        ## comment          # E266
        # comment           # OK
        ### header ###      # OK (separator)
    """

    code: ClassVar[str] = "E266"
    message: ClassVar[str] = "too many leading '#' for block comment"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        comment_start = info.comment_start
        if comment_start < 0:
            return
        leading_hashes = info.leading_hashes
        if leading_hashes != 2:
            return  # only flag exactly "##", not "###" separators
        char_after_hash = info.char_after_hash
        if char_after_hash == 0 or char_after_hash == ord("#"):
            return
        yield self.diagnostic_at(
            lineno,
            comment_start,
            fix=self._make_fix(lineno, comment_start, ctx),
        )

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        if comment_pos < 0:
            return
        comment = line[comment_pos:]
        hash_count = 0
        for char in comment:
            if char == "#":
                hash_count += 1
            else:
                break
        if hash_count == 2:
            rest = comment[hash_count:].strip()
            if rest and not rest.startswith("#"):
                yield self.diagnostic_at(
                    lineno,
                    comment_pos,
                    fix=self._make_fix(lineno, comment_pos, ctx),
                )

    def _make_fix(self, lineno: int, comment_pos: int, ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        start = line_start + comment_pos
        end = start + 2  # The "##"
        return Fix(description="Replace ## with #", edits=(Edit(start, end, "# "),))


# ─────────────────────────────────────────────────────────────────────────────
# E221-E224: Whitespace around operators (optimized with LineRule)
# ─────────────────────────────────────────────────────────────────────────────

# Operator pattern shared by E221-E224
_OPERATOR_PATTERN = r"[-+*/%@&|^<>=!]+|:=|\*\*|//"

# E221: Multiple spaces (no tabs) before operator
_E221_PATTERN = re.compile(rf"[^\s]( {{2,}})({_OPERATOR_PATTERN})")

# E222: Multiple spaces (no tabs) after operator
_E222_PATTERN = re.compile(rf"({_OPERATOR_PATTERN})( {{2,}})[^\s]")

# E223: Tab before operator
_E223_PATTERN = re.compile(rf"[^\s](\s*\t\s*)({_OPERATOR_PATTERN})")

# E224: Tab after operator
_E224_PATTERN = re.compile(rf"({_OPERATOR_PATTERN})(\s*\t\s*)[^\s]")


class MultipleSpacesBeforeOperator(LineRule):
    """
    E221: Multiple spaces before operator.

    Rationale: PEP 8 requires exactly one space around operators
    (except for alignment, which is discouraged).

    Example::

        a = 4  + 5      # E221
        a = 4 + 5       # OK
    """

    code: ClassVar[str] = "E221"
    message: ClassVar[str] = "multiple spaces before operator"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        if not (info.style_flags & _DOUBLE_SPACE_AROUND_OP):
            return
        line = ctx.text_lines[lineno - 1]
        comment_pos = info.comment_start
        yield from self.check_line(line, lineno, ctx, comment_pos=comment_pos)

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        code = line[:comment_pos] if comment_pos >= 0 else line

        for match in _E221_PATTERN.finditer(code):
            col = match.start(1)
            yield self.diagnostic_at(
                lineno,
                col,
                fix=self._make_fix(lineno, match, ctx),
            )

    def _make_fix(self, lineno: int, match: re.Match[str], ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        start = line_start + match.start(1)
        end = line_start + match.end(1)
        return Fix(description="Replace with single space", edits=(Edit(start, end, " "),))


class MultipleSpacesAfterOperator(LineRule):
    """
    E222: Multiple spaces after operator.

    Rationale: PEP 8 requires exactly one space around operators.

    Example::

        a = 4 +  5      # E222
        a = 4 + 5       # OK
    """

    code: ClassVar[str] = "E222"
    message: ClassVar[str] = "multiple spaces after operator"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        if not (info.style_flags & _DOUBLE_SPACE_AROUND_OP):
            return
        line = ctx.text_lines[lineno - 1]
        comment_pos = info.comment_start
        yield from self.check_line(line, lineno, ctx, comment_pos=comment_pos)

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        code = line[:comment_pos] if comment_pos >= 0 else line

        for match in _E222_PATTERN.finditer(code):
            col = match.start(2)
            yield self.diagnostic_at(
                lineno,
                col,
                fix=self._make_fix(lineno, match, ctx),
            )

    def _make_fix(self, lineno: int, match: re.Match[str], ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        start = line_start + match.start(2)
        end = line_start + match.end(2)
        return Fix(description="Replace with single space", edits=(Edit(start, end, " "),))


class TabBeforeOperator(LineRule):
    """
    E223: Tab before operator.

    Rationale: PEP 8 requires spaces, not tabs, around operators.

    Example::

        a = 4\\t+ 5     # E223
        a = 4 + 5       # OK
    """

    code: ClassVar[str] = "E223"
    message: ClassVar[str] = "tab before operator"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        if not (info.style_flags & _TAB_AROUND_OP):
            return
        line = ctx.text_lines[lineno - 1]
        comment_pos = info.comment_start
        yield from self.check_line(line, lineno, ctx, comment_pos=comment_pos)

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        code = line[:comment_pos] if comment_pos >= 0 else line

        for match in _E223_PATTERN.finditer(code):
            col = match.start(1)
            yield self.diagnostic_at(
                lineno,
                col,
                fix=self._make_fix(lineno, match, ctx),
            )

    def _make_fix(self, lineno: int, match: re.Match[str], ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        start = line_start + match.start(1)
        end = line_start + match.end(1)
        return Fix(description="Replace tab with space", edits=(Edit(start, end, " "),))


class TabAfterOperator(LineRule):
    """
    E224: Tab after operator.

    Rationale: PEP 8 requires spaces, not tabs, around operators.

    Example::

        a = 4 +\\t5     # E224
        a = 4 + 5       # OK
    """

    code: ClassVar[str] = "E224"
    message: ClassVar[str] = "tab after operator"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        if not (info.style_flags & _TAB_AROUND_OP):
            return
        line = ctx.text_lines[lineno - 1]
        comment_pos = info.comment_start
        yield from self.check_line(line, lineno, ctx, comment_pos=comment_pos)

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        code = line[:comment_pos] if comment_pos >= 0 else line

        for match in _E224_PATTERN.finditer(code):
            col = match.start(2)
            yield self.diagnostic_at(
                lineno,
                col,
                fix=self._make_fix(lineno, match, ctx),
            )

    def _make_fix(self, lineno: int, match: re.Match[str], ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        start = line_start + match.start(2)
        end = line_start + match.end(2)
        return Fix(description="Replace tab with space", edits=(Edit(start, end, " "),))


# ─────────────────────────────────────────────────────────────────────────────
# E225-E228: Missing whitespace around operators
# ─────────────────────────────────────────────────────────────────────────────


class MissingWhitespaceAroundOperator(Rule):
    """
    E225: Missing whitespace around operator.

    Rationale: PEP 8 requires spaces around assignment, comparison, and
    binary operators for readability.

    Example::

        i=i+1           # E225
        i = i + 1       # OK
    """

    code: ClassVar[str] = "E225"
    message: ClassVar[str] = "missing whitespace around operator"
    node_types = {
        NodeType.BINARY_OPERATOR,
        NodeType.AUGMENTED_ASSIGNMENT,
        NodeType.COMPARISON_OPERATOR,
        NodeType.ASSIGNMENT,
    }

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Skip slices and default parameters
        if node.parent_type in (
            "slice",
            "default_parameter",
            "typed_default_parameter",
            "keyword_argument",
        ):
            return

        children = node.children
        if len(children) < 3:
            return

        # Find the operator
        for i, child in enumerate(children):
            if child.type in (
                "+",
                "-",
                "*",
                "/",
                "//",
                "%",
                "**",
                "@",
                "+=",
                "-=",
                "*=",
                "/=",
                "//=",
                "%=",
                "**=",
                "@=",
                "&=",
                "|=",
                "^=",
                ">>=",
                "<<=",
                "==",
                "!=",
                "<",
                ">",
                "<=",
                ">=",
                ":=",
                "=",
            ):
                # Check space before
                if i > 0:
                    prev = children[i - 1]
                    if prev.line == child.line and child.column == prev.end_column:
                        yield self.diagnostic(child)
                        return

                # Check space after
                if i + 1 < len(children):
                    next_child = children[i + 1]
                    if next_child.line == child.line and next_child.column == child.end_column:
                        yield self.diagnostic(child)
                        return


class MissingWhitespaceAroundArithmeticOperator(Rule):
    """
    E226: Missing whitespace around arithmetic operator.

    Rationale: PEP 8 allows omitting spaces around arithmetic operators
    for grouping, but consistent spacing improves readability.
    This rule is ignored by default per pycodestyle convention.

    Example::

        c = (a+b) * (a-b)   # E226
        c = (a + b) * (a - b)   # OK
    """

    code: ClassVar[str] = "E226"
    message: ClassVar[str] = "missing whitespace around arithmetic operator"
    node_types = {NodeType.BINARY_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        parent = node.parent
        if parent and parent.type in ("slice",):
            return

        children = node.children
        if len(children) < 3:
            return

        # Check for arithmetic operators: +, -, *, /, //, **, @
        for i, child in enumerate(children):
            if child.type in ("+", "-", "*", "/", "//", "**", "@"):
                # Exclude unary operators
                if i == 0:
                    continue

                prev = children[i - 1]
                next_child = children[i + 1] if i + 1 < len(children) else None

                # Check missing space before
                if prev.line == child.line and child.column == prev.end_column:
                    yield self.diagnostic(child)
                    return

                # Check missing space after
                if (
                    next_child
                    and next_child.line == child.line
                    and next_child.column == child.end_column
                ):
                    yield self.diagnostic(child)
                    return


class MissingWhitespaceAroundBitwiseOperator(Rule):
    """
    E227: Missing whitespace around bitwise or shift operator.

    Rationale: PEP 8 requires spaces around bitwise and shift operators
    for readability.

    Example::

        x = x|y         # E227
        x = x | y       # OK
    """

    code: ClassVar[str] = "E227"
    message: ClassVar[str] = "missing whitespace around bitwise or shift operator"
    node_types = {NodeType.BINARY_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        children = node.children
        if len(children) < 3:
            return

        for i, child in enumerate(children):
            if child.type in ("&", "|", "^", "<<", ">>"):
                if i == 0:
                    continue

                prev = children[i - 1]
                next_child = children[i + 1] if i + 1 < len(children) else None

                if prev.line == child.line and child.column == prev.end_column:
                    yield self.diagnostic(child)
                    return

                if (
                    next_child
                    and next_child.line == child.line
                    and next_child.column == child.end_column
                ):
                    yield self.diagnostic(child)
                    return


class MissingWhitespaceAroundModuloOperator(Rule):
    """
    E228: Missing whitespace around modulo operator.

    Rationale: PEP 8 requires spaces around the modulo operator for
    readability.

    Example::

        x = x%y         # E228
        x = x % y       # OK
    """

    code: ClassVar[str] = "E228"
    message: ClassVar[str] = "missing whitespace around modulo operator"
    node_types = {NodeType.BINARY_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        children = node.children
        if len(children) < 3:
            return

        for i, child in enumerate(children):
            if child.type == "%":
                if i == 0:
                    continue

                prev = children[i - 1]
                next_child = children[i + 1] if i + 1 < len(children) else None

                if prev.line == child.line and child.column == prev.end_column:
                    yield self.diagnostic(child)
                    return

                if (
                    next_child
                    and next_child.line == child.line
                    and next_child.column == child.end_column
                ):
                    yield self.diagnostic(child)
                    return


# ─────────────────────────────────────────────────────────────────────────────
# E241-E242: Multiple spaces/tab after comma (optimized with LineRule)
# ─────────────────────────────────────────────────────────────────────────────

# E241: Multiple spaces (no tabs) after comma/semicolon
_E241_PATTERN = re.compile(r"([,;])( {2,})[^\s]")

# E242: Tab after comma/semicolon
_E242_PATTERN = re.compile(r"([,;])(\s*\t\s*)[^\s]")


class MultipleSpacesAfterComma(LineRule):
    """
    E241: Multiple spaces after ',', ';', or ':'.

    Rationale: PEP 8 requires exactly one space after commas and
    semicolons. This rule is ignored by default per pycodestyle
    convention.

    Example::

        a = (1,  2)     # E241
        a = (1, 2)      # OK
    """

    code: ClassVar[str] = "E241"
    message: ClassVar[str] = "multiple spaces after '{char}'"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        if not (info.style_flags & _DOUBLE_SPACE_AFTER_COMMA):
            return
        line = ctx.text_lines[lineno - 1]
        comment_pos = info.comment_start
        yield from self.check_line(line, lineno, ctx, comment_pos=comment_pos)

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        code = line[:comment_pos] if comment_pos >= 0 else line

        for match in _E241_PATTERN.finditer(code):
            char = match.group(1)
            col = match.start(2)
            yield self.diagnostic_at(
                lineno,
                col,
                self.message.format(char=char),
                fix=self._make_fix(lineno, match, ctx),
            )

    def _make_fix(self, lineno: int, match: re.Match[str], ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        start = line_start + match.start(2)
        end = line_start + match.end(2)
        return Fix(description="Replace with single space", edits=(Edit(start, end, " "),))


class TabAfterComma(LineRule):
    """
    E242: Tab after ',', ';', or ':'.

    Rationale: PEP 8 requires spaces, not tabs, after commas and
    semicolons. This rule is ignored by default per pycodestyle
    convention.

    Example::

        a = (1,\\t2)    # E242
        a = (1, 2)      # OK
    """

    code: ClassVar[str] = "E242"
    message: ClassVar[str] = "tab after '{char}'"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        if not (info.style_flags & _TAB_AFTER_COMMA):
            return
        line = ctx.text_lines[lineno - 1]
        comment_pos = info.comment_start
        yield from self.check_line(line, lineno, ctx, comment_pos=comment_pos)

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        code = line[:comment_pos] if comment_pos >= 0 else line

        for match in _E242_PATTERN.finditer(code):
            char = match.group(1)
            col = match.start(2)
            yield self.diagnostic_at(
                lineno,
                col,
                self.message.format(char=char),
                fix=self._make_fix(lineno, match, ctx),
            )

    def _make_fix(self, lineno: int, match: re.Match[str], ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        start = line_start + match.start(2)
        end = line_start + match.end(2)
        return Fix(description="Replace tab with space", edits=(Edit(start, end, " "),))


# ─────────────────────────────────────────────────────────────────────────────
# E271-E275: Whitespace around keywords (optimized with LineRule)
# ─────────────────────────────────────────────────────────────────────────────
#
# These rules use LineRule for efficient single-pass line iteration.
# Patterns are pre-compiled at class level with all keywords combined.

_KEYWORDS = (
    "and",
    "or",
    "not",
    "in",
    "is",
    "if",
    "elif",
    "else",
    "for",
    "while",
    "with",
    "as",
    "try",
    "except",
    "finally",
    "return",
    "yield",
    "import",
    "from",
    "def",
    "class",
    "lambda",
    "raise",
    "assert",
    "global",
    "nonlocal",
    "pass",
    "break",
    "continue",
    "async",
    "await",
)

_BINARY_KEYWORDS = ("and", "or", "in", "is", "not", "if", "else")

# Pre-compiled patterns with all keywords combined (single regex per rule)
_KEYWORDS_PATTERN = "|".join(_KEYWORDS)
_BINARY_KEYWORDS_PATTERN = "|".join(_BINARY_KEYWORDS)

# E271: keyword followed by 2+ spaces (not tabs) then non-space/colon
_E271_PATTERN = re.compile(rf"(?<![a-zA-Z_])({_KEYWORDS_PATTERN})( {{2,}})[^\s:]")

# E272: 2+ spaces (not tabs) before binary keyword
_E272_PATTERN = re.compile(rf"[^\s]( {{2,}})({_BINARY_KEYWORDS_PATTERN})(?![a-zA-Z_])")

# E273: keyword followed by tab
_E273_PATTERN = re.compile(rf"(?<![a-zA-Z_])({_KEYWORDS_PATTERN})(\s*\t\s*)[^\s:]")

# E274: tab before binary keyword
_E274_PATTERN = re.compile(rf"[^\s](\s*\t\s*)({_BINARY_KEYWORDS_PATTERN})(?![a-zA-Z_])")


class MultipleSpacesAfterKeyword(LineRule):
    """
    E271: Multiple spaces after keyword.

    Rationale: PEP 8 requires exactly one space after keywords.

    Example::

        if  x:          # E271
        if x:           # OK
    """

    code: ClassVar[str] = "E271"
    message: ClassVar[str] = "multiple spaces after keyword"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        if not (info.style_flags & _DOUBLE_SPACE_AROUND_KW):
            return
        line = ctx.text_lines[lineno - 1]
        comment_pos = info.comment_start
        yield from self.check_line(line, lineno, ctx, comment_pos=comment_pos)

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        code = line[:comment_pos] if comment_pos >= 0 else line

        for match in _E271_PATTERN.finditer(code):
            col = match.start(2)
            yield self.diagnostic_at(
                lineno,
                col,
                fix=self._make_fix(lineno, match, ctx),
            )

    def _make_fix(self, lineno: int, match: re.Match[str], ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        start = line_start + match.start(2)
        end = line_start + match.end(2)
        return Fix(description="Replace with single space", edits=(Edit(start, end, " "),))


class MultipleSpacesBeforeKeyword(LineRule):
    """
    E272: Multiple spaces before keyword.

    Rationale: PEP 8 requires exactly one space before keywords.

    Example::

        True  and False     # E272
        True and False      # OK
    """

    code: ClassVar[str] = "E272"
    message: ClassVar[str] = "multiple spaces before keyword"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        if not (info.style_flags & _DOUBLE_SPACE_AROUND_KW):
            return
        line = ctx.text_lines[lineno - 1]
        comment_pos = info.comment_start
        yield from self.check_line(line, lineno, ctx, comment_pos=comment_pos)

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        code = line[:comment_pos] if comment_pos >= 0 else line

        for match in _E272_PATTERN.finditer(code):
            col = match.start(1)
            yield self.diagnostic_at(
                lineno,
                col,
                fix=self._make_fix(lineno, match, ctx),
            )

    def _make_fix(self, lineno: int, match: re.Match[str], ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        start = line_start + match.start(1)
        end = line_start + match.end(1)
        return Fix(description="Replace with single space", edits=(Edit(start, end, " "),))


class TabAfterKeyword(LineRule):
    """
    E273: Tab after keyword.

    Rationale: PEP 8 requires spaces, not tabs, after keywords.

    Example::

        if\\tx:         # E273
        if x:           # OK
    """

    code: ClassVar[str] = "E273"
    message: ClassVar[str] = "tab after keyword"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        if not (info.style_flags & _TAB_AROUND_KW):
            return
        line = ctx.text_lines[lineno - 1]
        comment_pos = info.comment_start
        yield from self.check_line(line, lineno, ctx, comment_pos=comment_pos)

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        code = line[:comment_pos] if comment_pos >= 0 else line

        for match in _E273_PATTERN.finditer(code):
            col = match.start(2)
            yield self.diagnostic_at(
                lineno,
                col,
                fix=self._make_fix(lineno, match, ctx),
            )

    def _make_fix(self, lineno: int, match: re.Match[str], ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        start = line_start + match.start(2)
        end = line_start + match.end(2)
        return Fix(description="Replace tab with space", edits=(Edit(start, end, " "),))


class TabBeforeKeyword(LineRule):
    """
    E274: Tab before keyword.

    Rationale: PEP 8 requires spaces, not tabs, before keywords.

    Example::

        True\\tand False    # E274
        True and False      # OK
    """

    code: ClassVar[str] = "E274"
    message: ClassVar[str] = "tab before keyword"
    uses_line_infos: ClassVar[bool] = True

    def check_line_info(
        self,
        lineno: int,
        info: LineInfo,
        ctx: FileContext,
    ) -> Iterator[Diagnostic]:
        if not (info.style_flags & _TAB_AROUND_KW):
            return
        line = ctx.text_lines[lineno - 1]
        comment_pos = info.comment_start
        yield from self.check_line(line, lineno, ctx, comment_pos=comment_pos)

    def check_line(
        self, line: str, lineno: int, ctx: FileContext, *, comment_pos: int = -1
    ) -> Iterator[Diagnostic]:
        code = line[:comment_pos] if comment_pos >= 0 else line

        for match in _E274_PATTERN.finditer(code):
            col = match.start(1)
            yield self.diagnostic_at(
                lineno,
                col,
                fix=self._make_fix(lineno, match, ctx),
            )

    def _make_fix(self, lineno: int, match: re.Match[str], ctx: FileContext) -> Fix:
        line_start = ctx.line_start_byte(lineno)
        start = line_start + match.start(1)
        end = line_start + match.end(1)
        return Fix(description="Replace tab with space", edits=(Edit(start, end, " "),))


_E275_PATTERN = re.compile(
    rb"\b(assert|del|elif|except|if|import|in|not|raise|return|while|yield|"
    rb"for|with|from|as|class|def|async|await|lambda|global|nonlocal)\("
)


class MissingWhitespaceAfterKeyword(Rule):
    """
    E275: Missing whitespace after keyword.

    Rationale: PEP 8 requires a space between keywords and opening
    parentheses.

    Uses regex + tree-sitter point check to avoid false positives in strings.
    This is 17x faster than token-based checking.

    Example::

        if(x):          # E275
        if (x):         # OK
        x = "if(x)"     # OK (no false positive)
    """

    code: ClassVar[str] = "E275"
    message: ClassVar[str] = "missing whitespace after keyword"
    # Run once per module
    node_types = {NodeType.MODULE}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        ctx = node.ctx
        source = ctx.source
        tree = ctx.tree

        for match in _E275_PATTERN.finditer(source):
            pos = match.start()
            ts_node = tree.root_node.descendant_for_byte_range(pos, pos + 1)
            if ts_node is None:
                continue
            if ts_node.type in ("string", "string_content", "comment"):
                continue
            parent = ts_node.parent
            if parent and parent.type in ("string", "comment"):
                continue

            line = source[:pos].count(b"\n") + 1
            line_start = source.rfind(b"\n", 0, pos) + 1
            col = pos - line_start

            # Insert position: just before the "("
            insert_pos = match.end() - 1

            yield Diagnostic(
                code=self.code,
                message=self.message,
                location=Location(line=line, column=col),
                severity=Severity.WARNING,
                fix=Fix(
                    description="Add space after keyword",
                    edits=(Edit(insert_pos, insert_pos, " "),),
                ),
            )


WHITESPACE_RULES = [
    WhitespaceAfterOpenBracket,
    WhitespaceBeforeCloseBracket,
    WhitespaceBeforeColon,
    WhitespaceBeforeParameters,
    # E221-E224
    MultipleSpacesBeforeOperator,
    MultipleSpacesAfterOperator,
    TabBeforeOperator,
    TabAfterOperator,
    # E225-E228
    MissingWhitespaceAroundOperator,
    MissingWhitespaceAroundArithmeticOperator,
    MissingWhitespaceAroundBitwiseOperator,
    MissingWhitespaceAroundModuloOperator,
    MissingWhitespaceAfterComma,
    # E241-E242
    MultipleSpacesAfterComma,
    TabAfterComma,
    UnexpectedSpacesAroundKeywordEquals,
    TwoSpacesBeforeInlineComment,
    InlineCommentShouldStartWithSpace,
    BlockCommentShouldStartWithSpace,
    TooManyHashesForBlockComment,
    # E271-E275
    MultipleSpacesAfterKeyword,
    MultipleSpacesBeforeKeyword,
    TabAfterKeyword,
    TabBeforeKeyword,
    MissingWhitespaceAfterKeyword,
]

__all__ = [
    "WHITESPACE_RULES",
    "BlockCommentShouldStartWithSpace",
    "InlineCommentShouldStartWithSpace",
    "MissingWhitespaceAfterComma",
    "MissingWhitespaceAfterKeyword",
    "MissingWhitespaceAroundArithmeticOperator",
    "MissingWhitespaceAroundBitwiseOperator",
    "MissingWhitespaceAroundModuloOperator",
    # E225-E228
    "MissingWhitespaceAroundOperator",
    # E241-E242
    "MultipleSpacesAfterComma",
    # E271-E275
    "MultipleSpacesAfterKeyword",
    "MultipleSpacesAfterOperator",
    "MultipleSpacesBeforeKeyword",
    # E221-E224
    "MultipleSpacesBeforeOperator",
    "TabAfterComma",
    "TabAfterKeyword",
    "TabAfterOperator",
    "TabBeforeKeyword",
    "TabBeforeOperator",
    "TooManyHashesForBlockComment",
    "TwoSpacesBeforeInlineComment",
    "UnexpectedSpacesAroundKeywordEquals",
    "WhitespaceAfterOpenBracket",
    "WhitespaceBeforeCloseBracket",
    "WhitespaceBeforeColon",
    "WhitespaceBeforeParameters",
]
