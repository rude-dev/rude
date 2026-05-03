"""
Template rules - configurable templates for common patterns.

These are opt-in (not enabled by default). Enable via select = ["EX"].
They require configuration in [tool.rude.rules.XXXX].
"""

from __future__ import annotations

from collections.abc import Iterator
from fnmatch import fnmatch
from typing import Any, ClassVar

from rude.core.node import Node
from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, FileContext, Fix


class RequireBaseClass(Rule):
    """
    Require classes matching a pattern to inherit from a specific base.

    Rationale: Enforcing a common base class ensures all implementations
    share required interfaces and lifecycle hooks.

    Config::

        [tool.rude.rules.EX001]
        pattern = "*Service"
        required_base = "BaseService"
        paths = ["src/services/"]

    Example::

        # Bad
        class UserService:
            ...

        # Good
        class UserService(BaseService):
            ...
    """

    code: ClassVar[str] = "EX001"
    message: ClassVar[str] = "Class '{name}' must inherit from {required_base}"
    node_types = {NodeType.CLASS_DEFINITION}

    pattern: str = "*"
    required_base: str = "object"
    paths: list[str] = []

    def configure(self, options: dict[str, Any]) -> None:
        self.pattern = options.get("pattern", self.pattern)
        self.required_base = options.get("required_base", self.required_base)
        self.paths = options.get("paths", self.paths)

    def should_check_file(self, ctx: FileContext) -> bool:
        return not self.paths or ctx.is_in_path(*self.paths)

    def check(self, node: Node) -> Iterator[Diagnostic]:
        name = node.name
        if not name or not fnmatch(name, self.pattern):
            return
        if not node.inherits_from(self.required_base):
            yield self.diagnostic(
                node, self.message.format(name=name, required_base=self.required_base)
            )


class RequireDecorator(Rule):
    """
    Require functions in specific paths to have a decorator.

    Rationale: Ensures cross-cutting concerns like logging, auth, or
    metrics are consistently applied to matching functions.

    Config:
        [tool.rude.rules.EX002]
        required_decorator = "audit_log"
        paths = ["src/api/"]
        exclude_pattern = "_*"

    Example::

        # Bad
        def create_user(request):
            ...

        # Good
        @audit_log
        def create_user(request):
            ...
    """

    code: ClassVar[str] = "EX002"
    message: ClassVar[str] = "Function '{name}' must have @{decorator}"
    node_types = {NodeType.FUNCTION_DEFINITION}

    required_decorator: str = ""
    paths: list[str] = []
    pattern: str = "*"
    exclude_pattern: str = "_*"

    def configure(self, options: dict[str, Any]) -> None:
        self.required_decorator = options.get("required_decorator", self.required_decorator)
        self.paths = options.get("paths", self.paths)
        self.pattern = options.get("pattern", self.pattern)
        self.exclude_pattern = options.get("exclude_pattern", self.exclude_pattern)

    def should_check_file(self, ctx: FileContext) -> bool:
        return bool(self.required_decorator) and (not self.paths or ctx.is_in_path(*self.paths))

    def check(self, node: Node) -> Iterator[Diagnostic]:
        name = node.name
        if not name:
            return
        if self.exclude_pattern and fnmatch(name, self.exclude_pattern):
            return
        if not fnmatch(name, self.pattern):
            return
        if not node.has_decorator(self.required_decorator):
            yield self.diagnostic(
                node,
                self.message.format(name=name, decorator=self.required_decorator),
                fix=Fix.add_decorator(node, self.required_decorator),
            )


class ForbiddenCall(Rule):
    """
    Forbid specific function calls in certain paths.

    Rationale: Prevents accidental use of debug helpers, unsafe
    functions, or deprecated APIs in production code.

    Config:
        [tool.rude.rules.EX003]
        forbidden = ["print", "pdb.set_trace"]
        paths = ["src/"]
        exclude_paths = ["src/scripts/", "tests/"]

    Example::

        # Bad
        print("debug info")

        # Good
        logger.debug("debug info")
    """

    code: ClassVar[str] = "EX003"
    message: ClassVar[str] = "Call to '{name}' is forbidden"
    node_types = {NodeType.CALL}

    forbidden: list[str] = []
    paths: list[str] = []
    exclude_paths: list[str] = []

    def configure(self, options: dict[str, Any]) -> None:
        self.forbidden = options.get("forbidden", self.forbidden)
        self.paths = options.get("paths", self.paths)
        self.exclude_paths = options.get("exclude_paths", self.exclude_paths)

    def should_check_file(self, ctx: FileContext) -> bool:
        if not self.forbidden:
            return False
        if self.exclude_paths and ctx.is_in_path(*self.exclude_paths):
            return False
        return not self.paths or ctx.is_in_path(*self.paths)

    def check(self, node: Node) -> Iterator[Diagnostic]:
        name = node.full_call_name or node.function_name
        if name and name in self.forbidden:
            yield self.diagnostic(node, self.message.format(name=name))


class RequireFields(Rule):
    """
    Require classes to have specific attributes.

    Rationale: Ensures data classes and models always declare required
    fields like timestamps or audit columns.

    Config::

        [tool.rude.rules.EX004]
        pattern = "*Model"
        required_fields = ["created_at", "updated_at"]
        paths = ["src/models/"]

    Example::

        # Bad
        class UserModel:
            name: str

        # Good
        class UserModel:
            name: str
            created_at: datetime
            updated_at: datetime
    """

    code: ClassVar[str] = "EX004"
    message: ClassVar[str] = "Class '{name}' missing field: {field}"
    node_types = {NodeType.CLASS_DEFINITION}

    pattern: str = "*"
    required_fields: list[str] = []
    paths: list[str] = []

    def configure(self, options: dict[str, Any]) -> None:
        self.pattern = options.get("pattern", self.pattern)
        self.required_fields = options.get("required_fields", self.required_fields)
        self.paths = options.get("paths", self.paths)

    def should_check_file(self, ctx: FileContext) -> bool:
        return bool(self.required_fields) and (not self.paths or ctx.is_in_path(*self.paths))

    def check(self, node: Node) -> Iterator[Diagnostic]:
        name = node.name
        if not name or not fnmatch(name, self.pattern):
            return
        body = node.body
        if not body:
            return

        # Track which required fields are still missing
        required = set(self.required_fields)
        if not required:
            return

        # Only iterate direct children (class body is flat for assignments)
        for child in body.named_children:
            if child.type == "expression_statement":
                # Assignment is inside expression_statement: `x = 1`
                expr_children = child.named_children
                if expr_children:
                    expr = expr_children[0]
                    if expr.type == "assignment":
                        left = expr.child_by_field("left")
                        if left and left.is_identifier:
                            required.discard(left.text)
                            if not required:
                                return  # Early exit - all fields found
            elif child.type == "assignment":
                # Annotated assignment at class level: `x: int = 1`
                left = child.child_by_field("left")
                if left and left.is_identifier:
                    required.discard(left.text)
                    if not required:
                        return  # Early exit - all fields found

        for field in required:
            yield self.diagnostic(node, self.message.format(name=name, field=field))


RULES = [RequireBaseClass, RequireDecorator, ForbiddenCall, RequireFields]
