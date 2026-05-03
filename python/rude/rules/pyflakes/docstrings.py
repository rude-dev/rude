"""
Docstring rules: doctest validation.

F721: DoctestSyntaxError - syntax error in doctest
"""

from __future__ import annotations

import ast
import doctest
from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Severity
from rude.utils import extract_string_content

if TYPE_CHECKING:
    from rude.core.node import Node


class DoctestSyntaxError(Rule):
    """
    F721: Syntax error in doctest.

    Rationale: Doctest examples with invalid syntax will fail when
    run, and may indicate stale or incorrect documentation.

    Example::

        # Bad
        def foo():
            '''
            >>> x = [1, 2, 3
            '''  # F721 - unclosed bracket in doctest
            pass

        # Good
        def foo():
            '''
            >>> x = [1, 2, 3]
            '''
            pass
    """

    code: ClassVar[str] = "F721"
    message: ClassVar[str] = "syntax error in doctest"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.STRING}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Check if this string is a docstring
        if not self._is_docstring(node):
            return

        # Extract string content
        content = extract_string_content(node.text)
        if content is None:
            return

        # Check for doctest examples
        # Skip if no doctest markers
        if ">>>" not in content:
            return

        # Parse doctest examples
        parser = doctest.DocTestParser()
        try:
            examples = parser.get_examples(content)
        except ValueError:
            # Invalid doctest format
            return

        # Check each example for syntax errors
        for example in examples:
            try:
                # Try to parse the source as Python
                ast.parse(example.source)
            except SyntaxError as e:
                # Calculate the line number
                # example.lineno is 0-indexed from start of docstring content
                # e.lineno is 1-indexed within the example
                example_line = example.lineno + 1  # 1-indexed
                error_offset = (e.lineno or 1) - 1
                actual_line = node.line + example_line + error_offset

                yield self.diagnostic_at(actual_line, 0, self.message)

    def _is_docstring(self, node: Node) -> bool:
        """Check if this string is a docstring."""
        # Quick-reject: docstrings are always in expression_statement
        if node.parent_type != "expression_statement":
            return False

        parent = node.parent
        if parent is None:
            return False
        gp = parent.parent
        if not gp:
            return False

        # Module-level docstring
        if gp.type == "module":
            # Check if this is the first statement
            for child in gp.children:
                if child.type == "expression_statement":
                    return child.raw.id == parent.raw.id
                # Skip comments
                if child.type == "comment":
                    continue
                # Any other statement means this is not the first
                return False
            return False

        # Function/class docstring
        if gp.type in ("function_definition", "class_definition"):
            # The docstring should be in the body block
            body = gp.child_by_field("body")
            if body and body.type == "block":
                # Check if this is the first statement in the block
                for child in body.children:
                    if child.type == "expression_statement":
                        return child.raw.id == parent.raw.id
                    # Skip comments, newlines
                    if child.type in ("comment", "\n"):
                        continue
                    if not child.raw.is_named:
                        continue
                    # Any other named node means this is not the first
                    return False

        # Also check if parent of expression_statement is a block
        if gp.type == "block":
            # Check if this is the first statement
            ggp = gp.parent
            if ggp and ggp.type in ("function_definition", "class_definition"):
                for child in gp.children:
                    if child.type == "expression_statement":
                        return child.raw.id == parent.raw.id
                    if child.type in ("comment", "\n"):
                        continue
                    if not child.raw.is_named:
                        continue
                    return False

        return False


DOCSTRING_RULES = [
    DoctestSyntaxError,
]

__all__ = [
    "DOCSTRING_RULES",
    "DoctestSyntaxError",
]
