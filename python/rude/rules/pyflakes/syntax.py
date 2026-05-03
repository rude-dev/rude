"""
Syntax rules: invalid or suspicious syntax patterns.

F601: MultiValueRepeatedKeyLiteral - duplicate literal key in dict
F602: MultiValueRepeatedKeyVariable - duplicate variable key in dict
F621: TooManyExpressionsInStarredAssignment
F622: TwoStarredExpressions
F631: AssertTuple - assert with non-empty tuple (always truthy)
F632: IsLiteral - use of `is` with a literal
F633: InvalidPrintSyntax - use of >> with print (Python 2 syntax)
F634: IfTuple - if with non-empty tuple condition (always truthy)
F831: DuplicateArgument - duplicate argument in function definition
F901: RaiseNotImplemented - raise NotImplemented instead of NotImplementedError
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Edit, Fix, Severity

if TYPE_CHECKING:
    from rude.core.node import Node


class TooManyExpressionsInStarredAssignment(Rule):
    """
    F621: Too many expressions in starred assignment target.

    Rationale: Python limits unpacking targets to 255 elements. This
    is a compile-time error caught statically.

    Example::

        # Bad
        a, *b, c, d, e, f, g, ... = items  # Too many targets

        # Good
        first, *rest = items
    """

    code: ClassVar[str] = "F621"
    message: ClassVar[str] = "too many expressions in star-unpacking assignment"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.ASSIGNMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        left = node.child_by_field("left")
        if not left:
            return

        # Count starred expressions and total elements
        starred_count = 0
        total_count = 0

        for name in self._extract_targets(left):
            total_count += 1
            if name.type == "list_splat_pattern":
                starred_count += 1

        # Python limit is 256 for tuple unpacking
        if starred_count > 0 and total_count > 256:
            yield self.diagnostic(left)

    def _extract_targets(self, node: Node) -> Iterator[Node]:
        """Extract all targets from unpacking pattern."""
        if node.type in ("identifier", "list_splat_pattern"):
            yield node
        elif node.type in ("tuple", "list", "tuple_pattern", "list_pattern", "pattern_list"):
            for child in node.named_children:
                yield from self._extract_targets(child)


class TwoStarredExpressions(Rule):
    """
    F622: Two or more starred expressions in assignment.

    Rationale: Python only allows one starred expression per
    assignment target. This is a ``SyntaxError``.

    Example::

        # Bad
        *a, *b = [1, 2, 3]  # F622 - two starred expressions

        # Good
        a, *b = [1, 2, 3]
    """

    code: ClassVar[str] = "F622"
    message: ClassVar[str] = "two or more starred expressions in assignment"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.ASSIGNMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        left = node.child_by_field("left")
        if not left:
            return

        starred_nodes = list(self._find_starred(left))
        if len(starred_nodes) >= 2:
            yield self.diagnostic(left)

    def _find_starred(self, node: Node) -> Iterator[Node]:
        """Find starred patterns in unpacking target."""
        if node.type == "list_splat_pattern":
            yield node
        elif node.type in ("tuple", "list", "tuple_pattern", "list_pattern", "pattern_list"):
            for child in node.named_children:
                yield from self._find_starred(child)


def _is_nonempty_tuple(node: Node) -> bool:
    """Check if node is a non-empty tuple (always truthy)."""
    if node.type != "tuple":
        return False
    elements = [c for c in node.named_children if c.type not in ("(", ")", ",")]
    return len(elements) > 0


class AssertTuple(Rule):
    """
    F631: Assert test is a non-empty tuple, which is always True.

    Rationale: A tuple like ``(x, y)`` is always truthy, so the
    assertion never fails. This is usually a misplaced comma.

    Example::

        # Bad
        assert (x, y)  # F631 - tuple is always truthy

        # Good
        assert x and y
    """

    code: ClassVar[str] = "F631"
    message: ClassVar[str] = "assertion test is a non-empty tuple, which is always True"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.ASSERT_STATEMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # assert_statement children: "assert" expression [expression]
        # First expression is the condition
        children = node.named_children
        if not children:
            return

        condition = children[0]
        if _is_nonempty_tuple(condition):
            yield self.diagnostic(condition)


class IfTuple(Rule):
    """
    F634: If test is a non-empty tuple, which is always True.

    Rationale: A non-empty tuple is always truthy, so the branch
    always executes. This is usually a misplaced comma.

    Example::

        # Bad
        if (x, y):  # F634 - tuple is always truthy
            pass

        # Good
        if x and y:
            pass
    """

    code: ClassVar[str] = "F634"
    message: ClassVar[str] = "if test is a non-empty tuple, which is always True"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.IF_STATEMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        condition = node.child_by_field("condition")
        if condition and _is_nonempty_tuple(condition):
            yield self.diagnostic(condition)

        # Also check elif clauses
        for child in node.named_children:
            if child.type == "elif_clause":
                elif_cond = child.child_by_field("condition")
                if elif_cond and _is_nonempty_tuple(elif_cond):
                    yield self.diagnostic(elif_cond)


class IsLiteral(Rule):
    """
    F632: Use of `is` or `is not` with a literal.

    Using `is` with literals can have surprising behavior due to
    Python's interning. Use `==` instead.

    Example::

        x is 1        # F632 - use `==` instead
        x is "foo"    # F632
        x is None     # OK - None is a singleton
        x is True     # OK - True/False are singletons
    """

    code: ClassVar[str] = "F632"
    message: ClassVar[str] = "use ==/!= to compare '{literal}', not is/is not"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.COMPARISON_OPERATOR}

    # Literals that are NOT safe to compare with `is`
    LITERAL_TYPES = {"integer", "float", "string", "concatenated_string"}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        children = node.children

        i = 0
        while i < len(children):
            child = children[i]

            # Determine if this is an "is" or "is not" operator
            if child.text == "is not":
                operator_text = "is not"
                replacement = "!="
                op_start = child.start_byte
                op_end = child.end_byte
            elif child.text == "is":
                # Check if next token is "not" (separate tokens)
                if i + 1 < len(children) and children[i + 1].text == "not":
                    operator_text = "is not"
                    replacement = "!="
                    op_start = child.start_byte
                    op_end = children[i + 1].end_byte
                else:
                    operator_text = "is"
                    replacement = "=="
                    op_start = child.start_byte
                    op_end = child.end_byte
            else:
                i += 1
                continue

            fix = Fix(
                description=f"Replace {operator_text!r} with {replacement!r}",
                edits=(Edit(op_start, op_end, replacement),),
            )

            # Check operand before
            if i > 0:
                left = children[i - 1]
                if left.type in self.LITERAL_TYPES:
                    yield self.diagnostic(
                        left,
                        self.message.format(literal=self._truncate(left.text)),
                        fix=fix,
                    )

            # Check operand after (skip past "not" if separate)
            right_idx = i + 1
            if operator_text == "is not" and child.text == "is":
                right_idx = i + 2  # Skip the separate "not" token
            if right_idx < len(children):
                right = children[right_idx]
                if right.type in self.LITERAL_TYPES:
                    yield self.diagnostic(
                        right,
                        self.message.format(literal=self._truncate(right.text)),
                        fix=fix,
                    )

            i += 1

    def _truncate(self, text: str, max_len: int = 20) -> str:
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text


class RaiseNotImplemented(Rule):
    """
    F901: `raise NotImplemented` should be `raise NotImplementedError`.

    NotImplemented is a special value used for binary operations,
    not an exception.

    Example::

        raise NotImplemented           # F901 - wrong!
        raise NotImplementedError()    # OK
        raise NotImplementedError      # OK
    """

    code: ClassVar[str] = "F901"
    message: ClassVar[str] = "raise NotImplemented should be raise NotImplementedError"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.RAISE_STATEMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Check what is being raised
        for child in node.named_children:
            if child.is_identifier and child.text == "NotImplemented":
                yield self.diagnostic(
                    child,
                    fix=Fix.replace(child, "NotImplementedError"),
                )
            elif child.is_call:
                func = child.child_by_field("function")
                if func and func.is_identifier and func.text == "NotImplemented":
                    yield self.diagnostic(
                        func,
                        fix=Fix.replace(func, "NotImplementedError"),
                    )


def _find_repeated_keys(
    node: Node,
    key_predicate: Callable[[Node], bool],
) -> Iterator[tuple[str, Node]]:
    """Yield (key_text, key_node) for repeated dict keys with different values."""
    key_occurrences: dict[str, list[tuple[str, Node]]] = {}

    for child in node.named_children:
        if child.type == "pair":
            key_node = child.child_by_field("key")
            value_node = child.child_by_field("value")
            if key_node and key_predicate(key_node):
                key_text = key_node.text
                value_text = value_node.text if value_node else ""
                key_occurrences.setdefault(key_text, []).append((value_text, key_node))

    for key_text, occurrences in key_occurrences.items():
        if len(occurrences) > 1:
            values = {v for v, _ in occurrences}
            if len(values) > 1:
                for _, key_node in occurrences:
                    yield key_text, key_node


class MultiValueRepeatedKeyLiteral(Rule):
    """
    F601: Dictionary literal contains repeated key (literal).

    Pyflakes reports ALL occurrences of a key when:
    - The key appears more than once
    - The values are different

    Example::

        {"a": 1, "a": 2}  # F601 - both "a" keys reported
        {"a": 1, "a": 1}  # OK - same value, no report
    """

    code: ClassVar[str] = "F601"
    message: ClassVar[str] = "dictionary key {key!r} repeated"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.DICTIONARY}

    _LITERAL_TYPES = frozenset({"string", "integer", "float", "true", "false", "none"})

    def check(self, node: Node) -> Iterator[Diagnostic]:
        for key_text, key_node in _find_repeated_keys(
            node, lambda k: k.type in self._LITERAL_TYPES
        ):
            yield self.diagnostic(key_node, self.message.format(key=key_text))


class MultiValueRepeatedKeyVariable(Rule):
    """
    F602: Dictionary literal contains repeated key (variable).

    Pyflakes reports ALL occurrences of a variable key when:
    - The variable key appears more than once
    - The values are different

    Example::

        x = "key"
        {x: 1, x: 2}  # F602 - both x keys reported
        {x: 1, x: 1}  # OK - same value, no report
    """

    code: ClassVar[str] = "F602"
    message: ClassVar[str] = "dictionary key variable {key!r} repeated"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.DICTIONARY}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        for key_text, key_node in _find_repeated_keys(node, lambda k: k.is_identifier):
            yield self.diagnostic(key_node, self.message.format(key=key_text))


class InvalidPrintSyntax(Rule):
    """
    F633: Use of >> is invalid with print function.

    In Python 2, `print >> file, data` was used to redirect print output.
    This syntax is invalid in Python 3.

    Example::

        print >> sys.stderr, "error"  # F633 - invalid syntax
        print("error", file=sys.stderr)  # OK - Python 3 syntax
    """

    code: ClassVar[str] = "F633"
    message: ClassVar[str] = "use of >> is invalid with print function"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.PRINT_STATEMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # tree-sitter parses `print >> file` as a print_statement with chevron child
        for child in node.named_children:
            if child.type == "chevron":
                yield self.diagnostic(node)
                return


class DuplicateArgument(Rule):
    """
    F831: Duplicate argument in function definition.

    Rationale: Duplicate parameter names cause a ``SyntaxError`` in
    Python 3.

    Example::

        # Bad
        def foo(a, a):  # F831 - duplicate argument 'a'
            pass

        # Good
        def foo(a, b):
            pass
    """

    code: ClassVar[str] = "F831"
    message: ClassVar[str] = "duplicate argument '{name}' in function definition"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.FUNCTION_DEFINITION, NodeType.LAMBDA}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        params_node = node.child_by_field("parameters")
        if not params_node:
            return

        seen_names: dict[str, Node] = {}

        for param in params_node.named_children:
            name = self._extract_param_name(param)
            if name:
                if name in seen_names:
                    yield self.diagnostic(
                        param,
                        self.message.format(name=name),
                    )
                else:
                    seen_names[name] = param

    def _extract_param_name(self, param: Node) -> str | None:
        """Extract parameter name from various parameter node types."""
        if param.is_identifier:
            return param.text
        if param.type in ("typed_parameter", "default_parameter", "typed_default_parameter"):
            name = param.child_by_field("name")
            return name.text if name else None
        if param.type in ("list_splat_pattern", "dictionary_splat_pattern"):
            for child in param.named_children:
                if child.is_identifier:
                    return child.text
        return None


SYNTAX_RULES = [
    TooManyExpressionsInStarredAssignment,
    TwoStarredExpressions,
    AssertTuple,
    IfTuple,
    IsLiteral,
    InvalidPrintSyntax,
    RaiseNotImplemented,
    MultiValueRepeatedKeyLiteral,
    MultiValueRepeatedKeyVariable,
    DuplicateArgument,
]

__all__ = [
    "SYNTAX_RULES",
    "AssertTuple",
    "DuplicateArgument",
    "IfTuple",
    "InvalidPrintSyntax",
    "IsLiteral",
    "MultiValueRepeatedKeyLiteral",
    "MultiValueRepeatedKeyVariable",
    "RaiseNotImplemented",
    "TooManyExpressionsInStarredAssignment",
    "TwoStarredExpressions",
]
