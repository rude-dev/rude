"""
Statement rules: E701-E704, E722, E731, E741-E743.

E701: multiple statements on one line (colon)
E702: multiple statements on one line (semicolon)
E703: statement ends with semicolon
E704: multiple statements on one line (def)
E722: bare except
E731: lambda assignment
E741-E743: ambiguous names
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Edit, Fix

if TYPE_CHECKING:
    from rude.core.node import Node


class MultipleStatementsOnOneLineColon(Rule):
    """
    E701: Multiple statements on one line (colon).

    Rationale: PEP 8 requires compound statements to have the body
    on a separate line for readability.

    Example::

        if x: return y      # E701

        if x:               # OK
            return y
    """

    code: ClassVar[str] = "E701"
    message: ClassVar[str] = "multiple statements on one line (colon)"
    node_types = {
        NodeType.IF_STATEMENT,
        NodeType.FOR_STATEMENT,
        NodeType.WHILE_STATEMENT,
        NodeType.WITH_STATEMENT,
        NodeType.TRY_STATEMENT,
        NodeType.EXCEPT_CLAUSE,
        NodeType.FINALLY_CLAUSE,
        NodeType.ELSE_CLAUSE,
        NodeType.ELIF_CLAUSE,
    }

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Check if statement body is on same line as header
        body = node.child_by_field("body") or node.child_by_field("consequence")
        if not body:
            # Try to find block child
            for child in node.named_children:
                if child.type == "block":
                    body = child
                    break

        if (
            body
            and body.line == node.line
            and (
                body.type != "block"
                or (body.named_children and body.named_children[0].line == node.line)
            )
        ):
            # Body is on same line - check if it's a simple statement, not a block
            yield self.diagnostic(node)


class MultipleStatementsOnOneLineSemicolon(Rule):
    """
    E702: Multiple statements on one line (semicolon).

    Rationale: PEP 8 discourages semicolons to separate statements.
    Use separate lines instead.

    Example::

        x = 1; y = 2        # E702

        x = 1               # OK
        y = 2
    """

    code: ClassVar[str] = "E702"
    message: ClassVar[str] = "multiple statements on one line (semicolon)"
    node_types = {
        NodeType.EXPRESSION_STATEMENT,
        NodeType.ASSIGNMENT,
        NodeType.RETURN_STATEMENT,
        NodeType.PASS_STATEMENT,
        NodeType.BREAK_STATEMENT,
        NodeType.CONTINUE_STATEMENT,
    }

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Check if there's a semicolon in the source after this statement on the same line
        ctx = node.ctx
        line = ctx.get_line(node.end_line)
        col = node.end_column

        # Look for semicolon after this node on same line
        remaining = line[col:]
        if ";" in remaining:
            # Check it's not in a string
            semicolon_pos = remaining.find(";")
            before_semi = remaining[:semicolon_pos].strip()
            if not before_semi or before_semi.isspace():
                yield self.diagnostic(node)


class StatementEndsWithSemicolon(Rule):
    """
    E703: Statement ends with semicolon.

    Rationale: Trailing semicolons are unnecessary in Python and are
    a common artifact from C/Java habits.

    Example::

        x = 1;              # E703

        x = 1               # OK
    """

    code: ClassVar[str] = "E703"
    message: ClassVar[str] = "statement ends with a semicolon"
    node_types = {NodeType.MODULE}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Only check at module level
        if node.parent_type is not None:
            return

        ctx = node.ctx
        string_lines = ctx.string_lines
        for lineno, line_bytes in enumerate(ctx.lines, 1):
            # Skip lines inside multi-line strings (SQL, docstrings, etc.)
            if lineno in string_lines:
                continue
            line = line_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
            stripped = line.rstrip()
            if not stripped.endswith(";"):
                continue
            # Skip comment lines
            lstripped = stripped.lstrip()
            if lstripped.startswith("#"):
                continue
            # Skip if semicolon is after a comment start
            code_part = stripped
            from rude.utils import find_comment_start

            comment_pos = find_comment_start(stripped)
            if comment_pos >= 0:
                code_part = stripped[:comment_pos].rstrip()
                if not code_part.endswith(";"):
                    continue
            semi_col = len(stripped) - 1
            # Edit offsets are in bytes; len(stripped) is a char count, so encode
            # the line to find the trailing ';' on non-ASCII lines (e.g. "café;").
            line_start = ctx.line_start_byte(lineno)
            semi_byte = line_start + len(stripped.encode("utf-8")) - 1
            fix = Fix(
                description="Remove trailing semicolon",
                edits=(Edit(semi_byte, semi_byte + 1, ""),),
            )
            yield self.diagnostic_at(lineno, semi_col, fix=fix)


class MultipleStatementsOnOneLineDef(Rule):
    """
    E704: Multiple statements on one line (def).

    Rationale: PEP 8 requires function bodies on a separate line for
    readability and consistent style.

    Example::

        def f(): return 1   # E704

        def f():            # OK
            return 1
    """

    code: ClassVar[str] = "E704"
    message: ClassVar[str] = "multiple statements on one line (def)"
    node_types = {NodeType.FUNCTION_DEFINITION}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        body = node.child_by_field("body")
        if body and body.line == node.line:
            yield self.diagnostic(node)


class BareExcept(Rule):
    """
    E722: Do not use bare 'except'.

    Rationale: A bare ``except:`` catches all exceptions including
    ``KeyboardInterrupt`` and ``SystemExit``, which is almost never
    intended.

    Example::

        try:
            x = 1
        except:             # E722
            pass

        try:
            x = 1
        except Exception:   # OK
            pass
    """

    code: ClassVar[str] = "E722"
    message: ClassVar[str] = "do not use bare 'except'"
    node_types = {NodeType.EXCEPT_CLAUSE}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Single pass: scan children between "except" and ":"
        found_except = False
        has_type = False
        except_node = None
        colon_node = None
        for child in node.children:
            if child.type == "except":
                found_except = True
                except_node = child
                continue
            if found_except:
                if child.type == ":":
                    colon_node = child
                    break
                if child.type == "as":
                    break  # "as" means type was already found
                if child.type != "comment":
                    has_type = True
                    break
        if not has_type and except_node and colon_node:
            fix = Fix(
                description="Replace bare except with except Exception",
                edits=(Edit(except_node.end_byte, colon_node.start_byte, " Exception"),),
            )
            yield self.diagnostic(node, fix=fix)


class LambdaAssignment(Rule):
    """
    E731: Do not assign a lambda expression, use a def.

    Rationale: Assigning a lambda defeats its purpose as an anonymous
    function. A ``def`` provides a name for tracebacks and is clearer.

    Example::

        f = lambda x: x + 1     # E731

        def f(x):               # OK
            return x + 1
    """

    code: ClassVar[str] = "E731"
    message: ClassVar[str] = "do not assign a lambda expression, use a def"
    node_types = {NodeType.ASSIGNMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        right = node.child_by_field("right")
        if right and right.type == "lambda":
            left = node.child_by_field("left")
            # Only flag simple name assignments (f = lambda: ...),
            # not attribute (obj.f = lambda: ...) or subscript assignments.
            if left and left.type == "identifier":
                yield self.diagnostic(node)


class AmbiguousVariableName(Rule):
    """
    E741: Ambiguous variable name.

    Rationale: The names ``l``, ``O``, ``I`` are easily confused with
    ``1``, ``0``, ``l`` in many fonts.

    Example::

        l = 1       # E741
        O = 2       # E741
        I = 3       # E741

        length = 1  # OK
    """

    code: ClassVar[str] = "E741"
    message: ClassVar[str] = "ambiguous variable name '{name}'"
    node_types = {NodeType.ASSIGNMENT, NodeType.FOR_STATEMENT, NodeType.WITH_STATEMENT}

    AMBIGUOUS_NAMES = {"l", "O", "I"}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if node.type == "assignment" or node.type == "for_statement":
            left = node.child_by_field("left")
            if left:
                yield from self._check_target(left)
        elif node.type == "with_statement":
            for child in node.named_children:
                if child.type == "with_clause":
                    for item in child.named_children:
                        if item.type == "with_item":
                            alias = item.child_by_field("alias")
                            if alias:
                                yield from self._check_target(alias)

    def _check_target(self, node: Node) -> Iterator[Diagnostic]:
        if node.is_identifier and node.text in self.AMBIGUOUS_NAMES:
            yield self.diagnostic(node, self.message.format(name=node.text))
        elif node.type in ("tuple", "list", "pattern_list", "tuple_pattern", "list_pattern"):
            for child in node.named_children:
                yield from self._check_target(child)


class AmbiguousClassName(Rule):
    """
    E742: Ambiguous class name.

    Rationale: Single-letter class names like ``I``, ``O``, ``l`` are
    easily confused with digits in many fonts.

    Example::

        class I:        # E742
            pass

        class Index:    # OK
            pass
    """

    code: ClassVar[str] = "E742"
    message: ClassVar[str] = "ambiguous class name '{name}'"
    node_types = {NodeType.CLASS_DEFINITION}

    AMBIGUOUS_NAMES = {"l", "O", "I"}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        name_node = node.child_by_field("name")
        if name_node and name_node.text in self.AMBIGUOUS_NAMES:
            yield self.diagnostic(name_node, self.message.format(name=name_node.text))


class AmbiguousFunctionName(Rule):
    """
    E743: Ambiguous function name.

    Rationale: Single-letter function names like ``I``, ``O``, ``l``
    are easily confused with digits in many fonts.

    Example::

        def l():        # E743
            pass

        def length():   # OK
            pass
    """

    code: ClassVar[str] = "E743"
    message: ClassVar[str] = "ambiguous function name '{name}'"
    node_types = {NodeType.FUNCTION_DEFINITION}

    AMBIGUOUS_NAMES = {"l", "O", "I"}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        name_node = node.child_by_field("name")
        if name_node and name_node.text in self.AMBIGUOUS_NAMES:
            yield self.diagnostic(name_node, self.message.format(name=name_node.text))


STATEMENT_RULES = [
    MultipleStatementsOnOneLineColon,
    MultipleStatementsOnOneLineSemicolon,
    StatementEndsWithSemicolon,
    MultipleStatementsOnOneLineDef,
    BareExcept,
    LambdaAssignment,
    AmbiguousVariableName,
    AmbiguousClassName,
    AmbiguousFunctionName,
]

__all__ = [
    "STATEMENT_RULES",
    "AmbiguousClassName",
    "AmbiguousFunctionName",
    "AmbiguousVariableName",
    "BareExcept",
    "LambdaAssignment",
    "MultipleStatementsOnOneLineColon",
    "MultipleStatementsOnOneLineDef",
    "MultipleStatementsOnOneLineSemicolon",
    "StatementEndsWithSemicolon",
]
