"""
McCabe complexity rule: C901.

C901: function is too complex
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic

if TYPE_CHECKING:
    from rude.core.node import Node


class FunctionTooComplex(Rule):
    """
    C901: Function is too complex (cyclomatic complexity).

    Cyclomatic complexity measures the number of independent paths through
    a function. High complexity indicates code that is hard to test and
    maintain.

    Complexity is calculated as:
        1 (base) + if + elif + for + while + except + ternary + case

    Example::

        # Bad
        def complex_function(x):    # C901 if complexity > threshold
            if x > 0:               # +1
                if x > 10:          # +1
                    return "big"
                elif x > 5:         # +1
                    return "medium"
            for i in range(x):      # +1
                if i % 2 == 0:      # +1
                    print(i)
            return "small"
            # Total: 1 + 5 = 6

        # Good - extract branches into helpers
        def process(x):
            if x > 0:
                return handle_positive(x)
            return handle_range(x)

    Configuration:
        [tool.rude.rules.C901]
        max_complexity = 10  # default
    """

    code: ClassVar[str] = "C901"
    message: ClassVar[str] = "'{name}' is too complex ({complexity})"
    node_types = {NodeType.FUNCTION_DEFINITION}

    max_complexity: int = 10

    # Node types that increase complexity (matches McCabe/flake8 semantics)
    DECISION_NODES = {
        "if_statement",
        "elif_clause",
        "for_statement",
        "while_statement",
        "except_clause",
        "conditional_expression",  # ternary: x if cond else y
        "case_clause",
    }

    def configure(self, options: dict[str, Any]) -> None:
        self.max_complexity = options.get("max_complexity", 10)

    _FUNC_TYPES = frozenset(("function_definition",))

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Skip if complexity checking is disabled
        if self.max_complexity < 0:
            return

        # Skip nested functions — their branches are counted as part of the
        # enclosing function's complexity (matching mccabe/flake8 behaviour).
        parent = node.raw.parent
        while parent is not None:
            if parent.type in self._FUNC_TYPES:
                return
            parent = parent.parent

        name_node = node.child_by_field("name")
        name = name_node.text if name_node else "<anonymous>"

        complexity = self._calculate_complexity(node)

        if complexity > self.max_complexity:
            yield self.diagnostic(
                node,
                self.message.format(name=name, complexity=complexity),
            )

    def _calculate_complexity(self, node: Node) -> int:
        """Calculate cyclomatic complexity of a function.

        Traverses the entire subtree including nested functions, matching
        mccabe/flake8 semantics where nested function branches count towards
        the enclosing function's complexity.
        """
        complexity = 1  # Base complexity
        cursor = node.raw.walk()
        decision_nodes = self.DECISION_NODES

        # Track root node ID to know when we're done
        root_node = cursor.node
        if root_node is None:
            return complexity
        root_id = root_node.id

        # Descend into children first (skip the root function node itself)
        if not cursor.goto_first_child():
            return complexity

        while True:
            current = cursor.node
            if current is None:
                return complexity
            node_type = current.type

            # Count complexity
            if node_type in decision_nodes:
                complexity += 1

            # Continue traversal: depth-first
            if cursor.goto_first_child():
                continue
            if cursor.goto_next_sibling():
                continue

            # Backtrack up the tree
            while cursor.goto_parent():
                parent = cursor.node
                if parent is not None and parent.id == root_id:
                    return complexity
                if cursor.goto_next_sibling():
                    break
            else:
                return complexity

        return complexity


COMPLEXITY_RULES = [
    FunctionTooComplex,
]

__all__ = [
    "COMPLEXITY_RULES",
    "FunctionTooComplex",
]
