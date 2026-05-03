"""
Pattern rules - detect code smells and complexity issues.

Enable via select = ["PAT"].
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, FileContext, Fix

if TYPE_CHECKING:
    from rude.core.node import Node


class TooManyParameters(Rule):
    """Functions with too many parameters.

    Rationale: Many parameters make a function hard to call correctly
    and often signal it is doing too much.

    Example::

        # Bad
        def create_user(name, email, age, role, dept, mgr):
            ...

        # Good
        def create_user(config: UserConfig):
            ...
    """

    code: ClassVar[str] = "PAT001"
    message: ClassVar[str] = "Function '{name}' has {count} parameters (max {max})"
    node_types = {NodeType.FUNCTION_DEFINITION}
    max_params: int = 5

    def configure(self, options: dict[str, Any]) -> None:
        self.max_params = options.get("max_params", self.max_params)

    def check(self, node: Node) -> Iterator[Diagnostic]:
        name = node.name or "function"
        count = node.parameter_count
        if count > self.max_params:
            yield self.diagnostic(
                node, self.message.format(name=name, count=count, max=self.max_params)
            )


class TooManyBranches(Rule):
    """Functions with too many branches (cyclomatic complexity).

    Rationale: Many branches make a function hard to test and reason
    about. Consider extracting branches into helper functions.

    Example::

        # Bad
        def process(x):
            if x > 0:
                if x > 10:
                    ...
                elif x > 5:
                    ...
            elif x < 0:
                ...

        # Good
        def process(x):
            if x > 10:
                return handle_large(x)
            if x > 0:
                return handle_positive(x)
            return handle_negative(x)
    """

    code: ClassVar[str] = "PAT002"
    message: ClassVar[str] = "Function '{name}' has {count} branches (max {max})"
    node_types = {NodeType.FUNCTION_DEFINITION}
    max_branches: int = 12

    def configure(self, options: dict[str, Any]) -> None:
        self.max_branches = options.get("max_branches", self.max_branches)

    def check(self, node: Node) -> Iterator[Diagnostic]:
        name = node.name or "function"
        count = self._count_branches(node)
        if count > self.max_branches:
            yield self.diagnostic(
                node, self.message.format(name=name, count=count, max=self.max_branches)
            )

    def _count_branches(self, node: Node) -> int:
        branch_types = {
            "if_statement",
            "elif_clause",
            "for_statement",
            "while_statement",
            "try_statement",
            "except_clause",
            "with_statement",
            "match_statement",
            "case_clause",
        }
        return sum(1 for c in self._walk(node) if c.type in branch_types)

    def _walk(self, node: Node) -> Iterator[Node]:
        """Walk descendants, skipping nested functions."""
        for child in node.children:
            # Don't count nested functions - they have their own branch count
            if child.type in ("function_definition", "lambda"):
                continue
            yield child
            yield from self._walk(child)


class DeepNesting(Rule):
    """Too deep nesting.

    Rationale: Deeply nested code is hard to follow. Use guard clauses
    and early returns to flatten control flow.

    Example::

        # Bad
        def process(x):
            if x:
                if x.valid:
                    if x.ready:
                        do_work(x)

        # Good
        def process(x):
            if not x or not x.valid or not x.ready:
                return
            do_work(x)
    """

    code: ClassVar[str] = "PAT003"
    message: ClassVar[str] = "Code nested {depth} levels deep (max {max})"
    node_types = {NodeType.FUNCTION_DEFINITION}
    max_depth: int = 4

    def configure(self, options: dict[str, Any]) -> None:
        self.max_depth = options.get("max_depth", self.max_depth)

    def check(self, node: Node) -> Iterator[Diagnostic]:
        max_found = self._find_max_depth(node, 0)
        if max_found > self.max_depth:
            yield self.diagnostic(node, self.message.format(depth=max_found, max=self.max_depth))

    def _find_max_depth(self, node: Node, current: int) -> int:
        nesting = {
            "if_statement",
            "for_statement",
            "while_statement",
            "try_statement",
            "with_statement",
        }
        max_d = current
        for c in node.children:
            # Don't count nested functions - they have their own nesting depth
            if c.type in ("function_definition", "lambda"):
                continue
            d = current + 1 if c.type in nesting else current
            max_d = max(max_d, self._find_max_depth(c, d))
        return max_d


class LongFunction(Rule):
    """Functions that are too long.

    Rationale: Long functions are harder to understand, test, and
    maintain. Extract logical sections into well-named helpers.

    Example::

        # Bad
        def process():
            # ... 80 lines of code ...
            pass

        # Good
        def process():
            validate_input()
            transform_data()
            save_results()
    """

    code: ClassVar[str] = "PAT004"
    message: ClassVar[str] = "Function '{name}' is {lines} lines (max {max})"
    node_types = {NodeType.FUNCTION_DEFINITION}
    max_lines: int = 50

    def configure(self, options: dict[str, Any]) -> None:
        self.max_lines = options.get("max_lines", self.max_lines)

    def check(self, node: Node) -> Iterator[Diagnostic]:
        name = node.name or "function"
        lines = node.end_line - node.line + 1
        if lines > self.max_lines:
            yield self.diagnostic(
                node, self.message.format(name=name, lines=lines, max=self.max_lines)
            )


class GodClass(Rule):
    """Classes with too many methods.

    Rationale: Too many methods signal too many responsibilities.
    Split into focused classes following the Single Responsibility
    Principle.

    Example::

        # Bad
        class UserManager:
            def create(self): ...
            def delete(self): ...
            def send_email(self): ...
            def generate_report(self): ...
            # ... 20 more methods ...

        # Good
        class UserRepository:
            def create(self): ...
            def delete(self): ...

        class UserNotifier:
            def send_email(self): ...
    """

    code: ClassVar[str] = "PAT005"
    message: ClassVar[str] = "Class '{name}' has {count} methods (max {max})"
    node_types = {NodeType.CLASS_DEFINITION}
    max_methods: int = 20

    def configure(self, options: dict[str, Any]) -> None:
        self.max_methods = options.get("max_methods", self.max_methods)

    def check(self, node: Node) -> Iterator[Diagnostic]:
        name = node.name or "class"
        body = node.body
        if not body:
            return
        count = sum(1 for c in body.children if c.is_function)
        if count > self.max_methods:
            yield self.diagnostic(
                node, self.message.format(name=name, count=count, max=self.max_methods)
            )


class NoPassInExcept(Rule):
    """Don't silently swallow exceptions.

    Rationale: Using ``pass`` in an except block hides errors and
    makes debugging difficult. At minimum, log the exception.

    Example::

        # Bad
        try:
            do_work()
        except Exception:
            pass

        # Good
        try:
            do_work()
        except Exception:
            logger.exception("do_work failed")
    """

    code: ClassVar[str] = "PAT006"
    message: ClassVar[str] = "Don't silently swallow exceptions; at least log them"
    node_types = {NodeType.EXCEPT_CLAUSE}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        body = node.child_by_field("body") or node.find_first("block")
        if not body:
            return
        stmts = [c for c in body.named_children if c.type != "comment"]
        if len(stmts) == 1 and stmts[0].is_pass:
            yield self.diagnostic(stmts[0])


class BareExcept(Rule):
    """Bare except catches too much.

    Rationale: A bare ``except:`` catches all exceptions including
    ``KeyboardInterrupt`` and ``SystemExit``, making it impossible
    to interrupt or stop the program gracefully.

    Example::

        # Bad
        try:
            do_work()
        except:
            handle_error()

        # Good
        try:
            do_work()
        except Exception:
            handle_error()
    """

    code: ClassVar[str] = "PAT007"
    message: ClassVar[str] = "Bare except catches too much; use 'except Exception:'"
    node_types = {NodeType.EXCEPT_CLAUSE}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        has_type = any(
            c.type in ("identifier", "tuple", "attribute")
            for c in node.children
            if c.type not in ("except", ":", "as", "block", "comment")
        )
        if not has_type:
            yield self.diagnostic(
                node,
                fix=Fix.replace(node, node.text.replace("except:", "except Exception:", 1)),
            )


class NoEval(Rule):
    """eval() is a security risk.

    Rationale: ``eval()`` executes arbitrary code and can be exploited
    for code injection attacks. Use ``ast.literal_eval()`` for parsing
    literals, or a safer alternative.

    Example::

        # Bad
        value = eval(user_input)

        # Good
        value = ast.literal_eval(user_input)
    """

    code: ClassVar[str] = "PAT008"
    message: ClassVar[str] = "eval() is a security risk; use ast.literal_eval() for literals"
    node_types = {NodeType.CALL}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if node.function_name == "eval":
            args = node.call_arguments
            arg_text = args[0].text if args else ""
            yield self.diagnostic(
                node,
                fix=Fix.replace(node, f"ast.literal_eval({arg_text})", imports=["ast"]),
            )


class NoExec(Rule):
    """exec() is a security risk.

    Rationale: ``exec()`` runs arbitrary code, making the program
    vulnerable to code injection. Use safer alternatives like
    ``importlib`` or a sandboxed evaluator.

    Example::

        # Bad
        exec(user_code)

        # Good
        module = importlib.import_module(module_name)
    """

    code: ClassVar[str] = "PAT009"
    message: ClassVar[str] = "exec() is a security risk; avoid dynamic code execution"
    node_types = {NodeType.CALL}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if node.function_name == "exec":
            yield self.diagnostic(node)


class NoAssertInProduction(Rule):
    """Assert statements removed with -O flag.

    Rationale: ``assert`` statements are stripped when Python runs with
    the ``-O`` flag, so they cannot be relied on for production checks.
    Use ``if``/``raise`` for validation instead.

    Example::

        # Bad
        assert user.is_admin, "Admin required"

        # Good
        if not user.is_admin:
            raise PermissionError("Admin required")
    """

    code: ClassVar[str] = "PAT010"
    message: ClassVar[str] = "assert removed with -O; use proper validation"
    node_types = {NodeType.ASSERT_STATEMENT}

    def should_check_file(self, ctx: FileContext) -> bool:
        return not ctx.is_test_file()

    def check(self, node: Node) -> Iterator[Diagnostic]:
        yield self.diagnostic(node)


RULES = [
    TooManyParameters,
    TooManyBranches,
    DeepNesting,
    LongFunction,
    GodClass,
    NoPassInExcept,
    BareExcept,
    NoEval,
    NoExec,
    NoAssertInProduction,
]
