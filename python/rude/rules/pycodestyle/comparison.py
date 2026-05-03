"""
Comparison rules: E711-E714, E721.

E711: comparison to None
E712: comparison to True/False
E713: not in test
E714: not is test
E721: type comparison
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Fix

if TYPE_CHECKING:
    from rude.core.node import Node


class ComparisonToNone(Rule):
    """
    E711: Comparison to None should use 'is' or 'is not'.

    Rationale: ``None`` is a singleton, so identity checks (``is``)
    are more correct and faster than equality checks (``==``).

    Example::

        x == None    # E711 - use 'x is None'
        x != None    # E711 - use 'x is not None'

        x is None    # OK
        x is not None  # OK
    """

    code: ClassVar[str] = "E711"
    message: ClassVar[str] = (
        "comparison to None should be 'if cond is None:' or 'if cond is not None:'"
    )
    node_types = {NodeType.COMPARISON_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        children = node.children
        i = 0
        while i < len(children):
            child = children[i]
            # Check for == or != operators
            if child.type in ("==", "!=") or child.text in ("==", "!="):
                # Check operand before
                if i > 0 and children[i - 1].type == "none":
                    yield self.diagnostic(
                        node,
                        fix=self._make_fix(node, children[i - 1], child.text == "=="),
                    )
                # Check operand after
                if i + 1 < len(children) and children[i + 1].type == "none":
                    yield self.diagnostic(
                        node,
                        fix=self._make_fix(node, children[i + 1], child.text == "=="),
                    )
            i += 1

    def _make_fix(self, node: Node, none_node: Node, is_equality: bool) -> Fix:
        """Create fix to replace == with is, or != with is not."""
        # Get the full comparison text and replace operator
        text = node.text
        new_text = text.replace("==", "is", 1) if is_equality else text.replace("!=", "is not", 1)
        return Fix.replace(node, new_text, description="Use 'is' for None comparison")


class ComparisonToTrueFalse(Rule):
    """
    E712: Comparison to True/False should use 'if cond:' or 'if not cond:'.

    Rationale: Comparing to ``True``/``False`` with ``==`` is
    redundant. Use the value directly in a boolean context.

    Example::

        x == True    # E712 - use 'if x:'
        x == False   # E712 - use 'if not x:'
        x != True    # E712 - use 'if not x:'

        if x:        # OK
        if not x:    # OK
        x is True    # OK for singletons
    """

    code: ClassVar[str] = "E712"
    message: ClassVar[str] = "comparison to True should be 'if cond:' or 'if cond is True:'"
    node_types = {NodeType.COMPARISON_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        children = node.children
        i = 0
        while i < len(children):
            child = children[i]
            if child.type in ("==", "!=") or child.text in ("==", "!="):
                # Check operand before
                if i > 0 and children[i - 1].type in ("true", "false"):
                    yield self.diagnostic(node)
                # Check operand after
                if i + 1 < len(children) and children[i + 1].type in ("true", "false"):
                    yield self.diagnostic(node)
            i += 1


class NotInTest(Rule):
    """
    E713: Test for membership should be 'not in'.

    Rationale: ``not x in y`` is harder to read than the idiomatic
    ``x not in y``.

    Example::

        not x in y      # E713 - use 'x not in y'

        x not in y      # OK
    """

    code: ClassVar[str] = "E713"
    message: ClassVar[str] = "test for membership should be 'not in'"
    node_types = {NodeType.NOT_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # not_operator has argument child
        for child in node.named_children:
            if child.type == "comparison_operator":
                # Check if comparison has 'in' operator
                for c in child.children:
                    if c.type == "in" or c.text == "in":
                        yield self.diagnostic(
                            node,
                            fix=self._make_fix(node, child),
                        )
                        return

    def _make_fix(self, not_node: Node, comp_node: Node) -> Fix:
        """Rewrite 'not x in y' as 'x not in y'."""
        children = comp_node.children
        parts = []
        for _i, c in enumerate(children):
            if c.type == "in" or c.text == "in":
                parts.append("not in")
            else:
                parts.append(c.text)
        new_text = " ".join(parts)
        return Fix.replace(not_node, new_text, description="Use 'not in' operator")


class NotIsTest(Rule):
    """
    E714: Test for object identity should be 'is not'.

    Rationale: ``not x is y`` is harder to read than the idiomatic
    ``x is not y``.

    Example::

        not x is y      # E714 - use 'x is not y'

        x is not y      # OK
    """

    code: ClassVar[str] = "E714"
    message: ClassVar[str] = "test for object identity should be 'is not'"
    node_types = {NodeType.NOT_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        for child in node.named_children:
            if child.type == "comparison_operator":
                has_is = False
                has_not = False
                for c in child.children:
                    if c.type == "is" or c.text == "is":
                        has_is = True
                    elif c.type == "not" or c.text == "not":
                        has_not = True
                if has_is and not has_not:
                    yield self.diagnostic(
                        node,
                        fix=self._make_fix(node, child),
                    )
                    return

    def _make_fix(self, not_node: Node, comp_node: Node) -> Fix:
        """Rewrite 'not x is y' as 'x is not y'."""
        children = comp_node.children
        parts = []
        for c in children:
            if c.type == "is" or c.text == "is":
                parts.append("is not")
            else:
                parts.append(c.text)
        new_text = " ".join(parts)
        return Fix.replace(not_node, new_text, description="Use 'is not' operator")


class TypeComparison(Rule):
    """
    E721: Do not compare types, use isinstance().

    Rationale: ``isinstance()`` correctly handles subclasses, while
    ``type()`` comparison does not.

    Example::

        type(x) == int       # E721 - use isinstance(x, int)
        type(x) == type(y)   # E721 - use isinstance(x, type(y))

        isinstance(x, int)   # OK
    """

    code: ClassVar[str] = "E721"
    message: ClassVar[str] = "do not compare types, use 'isinstance()'"
    node_types = {NodeType.COMPARISON_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        children = node.children
        i = 0
        while i < len(children):
            child = children[i]
            if child.type in ("==", "!=") or child.text in ("==", "!="):
                # Check if either operand is type() call
                has_type_call = False
                if i > 0 and self._is_type_call(children[i - 1]):
                    has_type_call = True
                if i + 1 < len(children) and self._is_type_call(children[i + 1]):
                    has_type_call = True
                if has_type_call:
                    yield self.diagnostic(node)
                    return
            i += 1

    def _is_type_call(self, node: Node) -> bool:
        """Check if node is a type() call."""
        if node.is_call:
            func = node.child_by_field("function")
            return func is not None and func.text == "type"
        return False


COMPARISON_RULES = [
    ComparisonToNone,
    ComparisonToTrueFalse,
    NotInTest,
    NotIsTest,
    TypeComparison,
]

__all__ = [
    "COMPARISON_RULES",
    "ComparisonToNone",
    "ComparisonToTrueFalse",
    "NotInTest",
    "NotIsTest",
    "TypeComparison",
]
