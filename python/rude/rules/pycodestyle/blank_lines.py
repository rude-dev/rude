"""
Blank lines rules: E3xx.

E301: expected 1 blank line, found 0
E302: expected 2 blank lines, found N
E303: too many blank lines (N)
E304: blank lines found after function decorator
E305: expected 2 blank lines after class or function definition, found N
E306: expected 1 blank line before a nested definition, found N
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic

if TYPE_CHECKING:
    from rude.core.node import Node


class ExpectedOneBlankLine(Rule):
    """
    E301: Expected 1 blank line, found 0.

    Rationale: PEP 8 requires one blank line between method
    definitions in a class for readability.

    Example::

        class Foo:
            def bar(self):
                pass
            def baz(self):    # E301
                pass

        class Foo:
            def bar(self):
                pass

            def baz(self):    # OK
                pass
    """

    code: ClassVar[str] = "E301"
    message: ClassVar[str] = "expected 1 blank line, found 0"
    node_types = {NodeType.FUNCTION_DEFINITION}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Only check methods inside a class
        if node.parent_type != "block":
            return

        parent = node.parent
        if parent is None:
            return
        grandparent = parent.parent
        if not grandparent or grandparent.type != "class_definition":
            return

        # Check if there's a previous sibling that's also a function
        prev = node.prev_sibling
        while prev and prev.type == "comment":
            prev = prev.prev_sibling

        if prev and prev.type == "function_definition":
            # Count blank lines between
            blank_lines = node.line - prev.end_line - 1
            if blank_lines < 1:
                yield self.diagnostic(node)


class ExpectedTwoBlankLines(Rule):
    """
    E302: Expected 2 blank lines, found N.

    Rationale: PEP 8 requires two blank lines before top-level
    function or class definitions.

    Example::

        def foo():
            pass
        def bar():      # E302
            pass

        def foo():
            pass


        def bar():      # OK
            pass
    """

    code: ClassVar[str] = "E302"
    message: ClassVar[str] = "expected 2 blank lines, found {found}"
    node_types = {NodeType.FUNCTION_DEFINITION, NodeType.CLASS_DEFINITION}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Only check top-level definitions
        if node.parent_type != "module":
            return

        # Find previous non-comment sibling
        prev = node.prev_sibling
        while prev and prev.type == "comment":
            prev = prev.prev_sibling

        if not prev:
            return  # First definition in file

        # Skip after module docstring (first statement being a string)
        if prev.type == "expression_statement":
            children = prev.named_children
            if children and children[0].type in ("string", "concatenated_string"):
                # Only skip if this is the first statement (module docstring)
                prev_prev = prev.prev_sibling
                if not prev_prev:
                    return

        # Count blank lines
        blank_lines = node.line - prev.end_line - 1

        # Account for decorators
        decorators = node.decorators
        if decorators:
            first_decorator = decorators[0]
            blank_lines = first_decorator.line - prev.end_line - 1

        if blank_lines < 2:
            yield self.diagnostic_at(node.line, 0, self.message.format(found=blank_lines))


class TooManyBlankLines(Rule):
    """
    E303: Too many blank lines (N).

    Rationale: PEP 8 limits consecutive blank lines to two at the
    top level and one inside functions/classes.

    Example::

        # Bad
        def foo():
            pass



        def bar():      # E303 - 3 blank lines
            pass

        # Good
        def foo():
            pass


        def bar():
            pass
    """

    code: ClassVar[str] = "E303"
    message: ClassVar[str] = "too many blank lines ({count})"
    node_types = {NodeType.MODULE}

    max_blank_lines: int = 2

    def configure(self, options: dict[str, Any]) -> None:
        self.max_blank_lines = options.get("max_blank_lines", 2)

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if node.parent_type is not None:
            return

        ctx = node.ctx
        lines = ctx.lines
        consecutive_blank = 0
        blank_start = 0

        for lineno, line in enumerate(lines, 1):
            is_blank = not line.strip()

            if is_blank:
                if consecutive_blank == 0:
                    blank_start = lineno
                consecutive_blank += 1
            else:
                if consecutive_blank > self.max_blank_lines:
                    yield self.diagnostic_at(
                        blank_start, 0, self.message.format(count=consecutive_blank)
                    )
                consecutive_blank = 0


class BlankLinesAfterDecorator(Rule):
    """
    E304: Blank lines found after function decorator.

    Rationale: A blank line between a decorator and the function it
    decorates is misleading and violates PEP 8.

    Example::

        @decorator

        def foo():      # E304
            pass

        @decorator
        def foo():      # OK
            pass
    """

    code: ClassVar[str] = "E304"
    message: ClassVar[str] = "blank lines found after function decorator"
    node_types = {NodeType.DECORATED_DEFINITION}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Find decorator and definition children
        decorators = []
        definition = None

        for child in node.named_children:
            if child.type == "decorator":
                decorators.append(child)
            elif child.type in ("function_definition", "class_definition"):
                definition = child

        if not decorators or not definition:
            return

        last_decorator = decorators[-1]

        # Check for blank lines between last decorator and definition
        blank_lines = definition.line - last_decorator.end_line - 1
        if blank_lines > 0:
            yield self.diagnostic_at(last_decorator.end_line + 1, 0)


class ExpectedTwoBlankLinesAfterClassOrFunction(Rule):
    """
    E305: Expected 2 blank lines after class or function definition.

    Rationale: PEP 8 requires two blank lines after top-level
    definitions to visually separate them from module-level code.

    Example::

        class Foo:
            pass
        x = 1           # E305

        class Foo:
            pass


        x = 1           # OK
    """

    code: ClassVar[str] = "E305"
    message: ClassVar[str] = (
        "expected 2 blank lines after class or function definition, found {found}"
    )
    node_types = {
        NodeType.EXPRESSION_STATEMENT,
        NodeType.ASSIGNMENT,
        NodeType.IMPORT_STATEMENT,
        NodeType.IMPORT_FROM_STATEMENT,
    }

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Only check top-level statements
        if node.parent_type != "module":
            return

        prev = node.prev_sibling
        while prev and prev.type == "comment":
            prev = prev.prev_sibling

        if not prev:
            return

        if prev.type not in ("function_definition", "class_definition"):
            return

        # Count blank lines
        blank_lines = node.line - prev.end_line - 1
        if blank_lines < 2:
            yield self.diagnostic_at(node.line, 0, self.message.format(found=blank_lines))


class ExpectedOneBlankLineBeforeNestedDef(Rule):
    """
    E306: Expected 1 blank line before a nested definition.

    Rationale: PEP 8 requires a blank line before a nested function
    or class to visually separate it from surrounding code.

    Example::

        def foo():
            x = 1
            def bar():      # E306
                pass

        def foo():
            x = 1

            def bar():      # OK
                pass
    """

    code: ClassVar[str] = "E306"
    message: ClassVar[str] = "expected 1 blank line before a nested definition, found {found}"
    node_types = {NodeType.FUNCTION_DEFINITION, NodeType.CLASS_DEFINITION}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Only check nested definitions (not top-level, not methods)
        if node.parent_type != "block":
            return

        parent = node.parent
        if parent is None:
            return
        grandparent = parent.parent
        if not grandparent:
            return

        # Skip if inside a class (that's E301's job)
        if grandparent.type == "class_definition":
            return

        # Must be inside a function
        if grandparent.type != "function_definition":
            return

        prev = node.prev_sibling
        while prev and prev.type == "comment":
            prev = prev.prev_sibling

        if not prev:
            return  # First statement in block

        # Count blank lines
        blank_lines = node.line - prev.end_line - 1

        # Account for decorators
        decorators = node.decorators
        if decorators:
            first_decorator = decorators[0]
            blank_lines = first_decorator.line - prev.end_line - 1

        if blank_lines < 1:
            yield self.diagnostic_at(node.line, 0, self.message.format(found=blank_lines))


BLANK_LINES_RULES = [
    ExpectedOneBlankLine,
    ExpectedTwoBlankLines,
    TooManyBlankLines,
    BlankLinesAfterDecorator,
    ExpectedTwoBlankLinesAfterClassOrFunction,
    ExpectedOneBlankLineBeforeNestedDef,
]

__all__ = [
    "BLANK_LINES_RULES",
    "BlankLinesAfterDecorator",
    "ExpectedOneBlankLine",
    "ExpectedOneBlankLineBeforeNestedDef",
    "ExpectedTwoBlankLines",
    "ExpectedTwoBlankLinesAfterClassOrFunction",
    "TooManyBlankLines",
]
