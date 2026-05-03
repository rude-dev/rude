"""
Control flow rules: statements in wrong context.

F701: BreakOutsideLoop
F702: ContinueOutsideLoop
F704: YieldOutsideFunction
F706: ReturnOutsideFunction
F707: DefaultExceptNotLast

F701-F706 use the ancestor context map from the Rust SemanticModel
when available, falling back to parent-walking for uncovered nodes.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Severity
from rude.providers import ScopeProvider
from rude.providers.semantic import CTX_IN_FUNCTION, CTX_IN_LAMBDA

if TYPE_CHECKING:
    from rude._rust import SemanticModel
    from rude.core.node import Node


def _get_model(node: Node) -> SemanticModel | None:
    """Try to get SemanticModel from context, returns None if unavailable."""
    try:
        sp: ScopeProvider = node.ctx.get_metadata(ScopeProvider)
        return sp.model
    except Exception:
        return None


class ReturnOutsideFunction(Rule):
    """
    F706: `return` statement outside of a function.

    Rationale: A ``return`` at module level is a ``SyntaxError``.

    Example::

        # Bad
        return 1  # F706 - not inside a function

        # Good
        def foo():
            return 1
    """

    code: ClassVar[str] = "F706"
    message: ClassVar[str] = "'return' outside function"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.RETURN_STATEMENT}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        model = _get_model(node)
        if model is not None:
            ctx = model.node_context(node.start_byte)
            if ctx is not None:
                flags, _, _ = ctx
                if not (flags & CTX_IN_FUNCTION):
                    yield self.diagnostic(node)
                return
        # Fallback: parent-walking
        if not self._has_function_ancestor(node):
            yield self.diagnostic(node)

    def _has_function_ancestor(self, node: Node) -> bool:
        current = node.parent
        while current:
            if current.type in ("function_definition", "lambda"):
                return True
            current = current.parent
        return False


class YieldOutsideFunction(Rule):
    """
    F704: `yield` or `yield from` outside of a function.

    Rationale: A ``yield`` at module level is a ``SyntaxError``.

    Example::

        # Bad
        yield 1  # F704 - not inside a function

        # Good
        def gen():
            yield 1
    """

    code: ClassVar[str] = "F704"
    message: ClassVar[str] = "'{keyword}' outside function"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.YIELD}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        model = _get_model(node)
        if model is not None:
            ctx = model.node_context(node.start_byte)
            if ctx is not None:
                flags, _, _ = ctx
                # yield is valid in function but NOT in lambda-only context
                in_function = bool(flags & CTX_IN_FUNCTION)
                in_lambda = bool(flags & CTX_IN_LAMBDA)
                if not in_function or in_lambda:
                    keyword = "yield from" if "from" in node.text else "yield"
                    yield self.diagnostic(node, self.message.format(keyword=keyword))
                return
        # Fallback: parent-walking
        if not self._has_function_ancestor(node):
            keyword = "yield from" if "from" in node.text else "yield"
            yield self.diagnostic(node, self.message.format(keyword=keyword))

    def _has_function_ancestor(self, node: Node) -> bool:
        current = node.parent
        while current:
            if current.type == "function_definition":
                return True
            current = current.parent
        return False


def _has_loop_ancestor(node: Node) -> bool:
    """Check if node is inside a loop, stopping at function boundaries."""
    current = node.parent
    while current:
        if current.type in ("for_statement", "while_statement"):
            return True
        if current.type in ("function_definition", "lambda"):
            return False
        current = current.parent
    return False


class ContinueOutsideLoop(Rule):
    """
    F702: `continue` not properly in loop.

    Rationale: ``continue`` outside a loop is a ``SyntaxError``.

    Example::

        # Bad
        continue  # F702 - not inside a loop

        # Good
        for i in range(10):
            continue
    """

    code: ClassVar[str] = "F702"
    message: ClassVar[str] = "'continue' not properly in loop"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.CONTINUE_STATEMENT}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        model = _get_model(node)
        if model is not None:
            if not model.is_in_loop(node.start_byte):
                yield self.diagnostic(node)
            return
        # Fallback: parent-walking
        if not _has_loop_ancestor(node):
            yield self.diagnostic(node)


class BreakOutsideLoop(Rule):
    """
    F701: `break` not properly in loop.

    Rationale: ``break`` outside a loop is a ``SyntaxError``.

    Example::

        # Bad
        break  # F701 - not inside a loop

        # Good
        while True:
            break
    """

    code: ClassVar[str] = "F701"
    message: ClassVar[str] = "'break' not properly in loop"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.BREAK_STATEMENT}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        model = _get_model(node)
        if model is not None:
            if not model.is_in_loop(node.start_byte):
                yield self.diagnostic(node)
            return
        # Fallback: parent-walking
        if not _has_loop_ancestor(node):
            yield self.diagnostic(node)


class DefaultExceptNotLast(Rule):
    """
    F707: A bare `except:` clause must be the last exception handler.

    Rationale: A bare ``except:`` before a typed handler is a
    ``SyntaxError`` because the typed handler would be unreachable.

    Example::

        # Bad
        try:
            pass
        except:        # F707 - bare except must be last
            pass
        except TypeError:
            pass

        # Good
        try:
            pass
        except TypeError:
            pass
        except:
            pass
    """

    code: ClassVar[str] = "F707"
    message: ClassVar[str] = "an except clause without an exception type must be last"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.TRY_STATEMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        except_clauses = [c for c in node.named_children if c.type == "except_clause"]

        # Find bare except clauses and check their positions
        for i, clause in enumerate(except_clauses):
            if self._is_bare_except(clause) and i < len(except_clauses) - 1:
                # If it's not the last one, it's an error
                yield self.diagnostic(clause)

    def _is_bare_except(self, clause: Node) -> bool:
        """Check if except clause has no exception type."""
        # A bare except has no children between 'except' and ':'
        # Structure: except_clause -> "except" ":" block
        # vs: except_clause -> "except" identifier ":" block
        return all(child.type == "block" for child in clause.named_children)


CONTROL_FLOW_RULES = [
    ReturnOutsideFunction,
    YieldOutsideFunction,
    ContinueOutsideLoop,
    BreakOutsideLoop,
    DefaultExceptNotLast,
]

__all__ = [
    "CONTROL_FLOW_RULES",
    "BreakOutsideLoop",
    "ContinueOutsideLoop",
    "DefaultExceptNotLast",
    "ReturnOutsideFunction",
    "YieldOutsideFunction",
]
