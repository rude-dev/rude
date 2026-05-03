"""
Annotation rules: type annotation validation.

F722: ForwardAnnotationSyntaxError - syntax error in forward annotation
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Severity
from rude.utils import extract_string_content

if TYPE_CHECKING:
    from rude.core.node import Node


class ForwardAnnotationSyntaxError(Rule):
    """
    F722: Syntax error in forward annotation.

    Rationale: A forward annotation with invalid syntax will raise a
    ``SyntaxError`` when evaluated at runtime or by type checkers.

    Example::

        # Bad
        x: "List[int"  # F722 - unclosed bracket

        # Good
        x: "List[int]"
    """

    code: ClassVar[str] = "F722"
    message: ClassVar[str] = "syntax error in forward annotation {annotation!r}"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.STRING}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Check if this string is in an annotation context
        if not self._is_annotation_context(node):
            return

        # Extract string content
        content = extract_string_content(node.text)
        if content is None:
            return

        # Try to parse as Python expression
        try:
            ast.parse(content, mode="eval")
        except SyntaxError:
            yield self.diagnostic(node, self.message.format(annotation=content))

    def _is_annotation_context(self, node: Node) -> bool:
        """Check if this string is used as a type annotation."""
        # Quick-reject: check parent type without inflating
        pt = node.parent_type
        if pt is None:
            return False

        # Direct annotation: x: "str"
        if pt == "type":
            return True

        # Function return type: def foo() -> "str":
        # The structure is: function_definition -> type -> string
        # But tree-sitter might wrap it differently
        if pt == "function_definition":
            parent = node.parent
            if parent is not None:
                # Check if this is the return type
                return_type = parent.child_by_field("return_type")
                if return_type and self._contains(return_type, node):
                    return True

        # Check for annotation context with intermediate nodes
        # Sometimes the structure is: type -> concatenated_string -> string
        if pt == "concatenated_string":
            parent = node.parent
            if parent is not None:
                gp = parent.parent
                if gp and gp.type == "type":
                    return True

        return False

    def _contains(self, container: Node, target: Node) -> bool:
        """Check if container contains target."""
        if container.raw.id == target.raw.id:
            return True
        return any(self._contains(child, target) for child in container.children)


ANNOTATION_RULES = [
    ForwardAnnotationSyntaxError,
]

__all__ = [
    "ANNOTATION_RULES",
    "ForwardAnnotationSyntaxError",
]
