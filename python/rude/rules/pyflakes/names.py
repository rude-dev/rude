"""
Name-related rules requiring scope analysis.

F821: UndefinedName - use of name that is not defined
F822: UndefinedExport - name in __all__ not defined in module
F823: UndefinedLocal - local variable used before assignment
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Severity
from rude.providers import NO_SCOPE, ScopeProvider

if TYPE_CHECKING:
    from rude.core.node import Node


# Python built-in names that are always available
BUILTINS = frozenset(
    {
        # Built-in functions
        "abs",
        "aiter",
        "all",
        "anext",
        "any",
        "ascii",
        "bin",
        "bool",
        "breakpoint",
        "bytearray",
        "bytes",
        "callable",
        "chr",
        "classmethod",
        "compile",
        "complex",
        "delattr",
        "dict",
        "dir",
        "divmod",
        "enumerate",
        "eval",
        "exec",
        "filter",
        "float",
        "format",
        "frozenset",
        "getattr",
        "globals",
        "hasattr",
        "hash",
        "help",
        "hex",
        "id",
        "input",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "locals",
        "map",
        "max",
        "memoryview",
        "min",
        "next",
        "object",
        "oct",
        "open",
        "ord",
        "pow",
        "print",
        "property",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "setattr",
        "slice",
        "sorted",
        "staticmethod",
        "str",
        "sum",
        "super",
        "tuple",
        "type",
        "vars",
        "zip",
        # Built-in exceptions
        "BaseException",
        "BaseExceptionGroup",
        "Exception",
        "ExceptionGroup",
        "ArithmeticError",
        "AssertionError",
        "AttributeError",
        "BlockingIOError",
        "BrokenPipeError",
        "BufferError",
        "BytesWarning",
        "ChildProcessError",
        "ConnectionAbortedError",
        "ConnectionError",
        "ConnectionRefusedError",
        "ConnectionResetError",
        "DeprecationWarning",
        "EOFError",
        "EnvironmentError",
        "FileExistsError",
        "FileNotFoundError",
        "FloatingPointError",
        "FutureWarning",
        "GeneratorExit",
        "IOError",
        "ImportError",
        "ImportWarning",
        "IndentationError",
        "IndexError",
        "InterruptedError",
        "IsADirectoryError",
        "KeyError",
        "KeyboardInterrupt",
        "LookupError",
        "MemoryError",
        "ModuleNotFoundError",
        "NameError",
        "NotADirectoryError",
        "NotImplemented",
        "NotImplementedError",
        "OSError",
        "OverflowError",
        "PendingDeprecationWarning",
        "PermissionError",
        "ProcessLookupError",
        "RecursionError",
        "ReferenceError",
        "ResourceWarning",
        "RuntimeError",
        "RuntimeWarning",
        "StopAsyncIteration",
        "StopIteration",
        "SyntaxError",
        "SyntaxWarning",
        "SystemError",
        "SystemExit",
        "TabError",
        "TimeoutError",
        "TypeError",
        "UnboundLocalError",
        "UnicodeDecodeError",
        "UnicodeEncodeError",
        "UnicodeError",
        "UnicodeTranslateError",
        "UnicodeWarning",
        "UserWarning",
        "ValueError",
        "Warning",
        "ZeroDivisionError",
        # Built-in constants
        "True",
        "False",
        "None",
        "Ellipsis",
        "__debug__",
        # Special names
        "__name__",
        "__doc__",
        "__package__",
        "__loader__",
        "__spec__",
        "__file__",
        "__cached__",
        "__builtins__",
        "__annotations__",
        "__import__",
        # Site-specific built-ins (added by site module)
        "exit",
        "quit",
        "copyright",
        "credits",
        "license",
    }
)


class UndefinedName(Rule):
    """
    F821: Name is not defined.

    Rationale: Using an undefined name causes a ``NameError`` at
    runtime.

    Example::

        # Bad
        print(undefined_variable)  # F821

        # Good
        x = 1
        print(x)

    Optimized to use pre-computed unresolved names from ScopeProvider.
    """

    code: ClassVar[str] = "F821"
    message: ClassVar[str] = "undefined name '{name}'"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.MODULE}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        from rude.core.types import Location

        scope_prov: ScopeProvider = node.ctx.get_metadata(ScopeProvider)
        model = scope_prov.model

        if model.module_scope == NO_SCOPE:
            return
        module_scope = model.scope(model.module_scope)

        # Iterate over pre-computed unresolved names
        # Note: Attribute accesses (obj.attr) are already filtered by ScopeProvider
        for uref in model.unresolved:
            # Skip builtins
            if uref.name in BUILTINS:
                continue

            # Skip private/dunder names (often dynamically set)
            if uref.name.startswith("_"):
                continue

            # Check if declared as global/nonlocal in containing scope
            scope = model.scope(uref.scope_id)
            if uref.name in scope.globals or uref.name in scope.nonlocals:
                continue

            # Skip if defined at module level (forward reference)
            # This handles cases like: def foo(): use_bar()  ...  def bar(): pass
            # But check if it's an exception handler that's no longer valid
            if uref.name in module_scope.bindings:
                binding = model.binding(module_scope.bindings[uref.name])
                # Exception handler variables are deleted after the except block
                if (
                    binding.valid_until_byte is not None
                    and uref.start_byte >= binding.valid_until_byte
                ):
                    yield Diagnostic(
                        code=self.code,
                        message=self.message.format(name=uref.name),
                        location=Location(line=uref.line, column=uref.column),
                        severity=self.severity,
                    )
                continue

            yield Diagnostic(
                code=self.code,
                message=self.message.format(name=uref.name),
                location=Location(line=uref.line, column=uref.column),
                severity=self.severity,
            )


class UndefinedExport(Rule):
    """
    F822: Name in __all__ is not defined.

    Rationale: Listing an undefined name in ``__all__`` causes an
    ``AttributeError`` when the module is imported with ``*``.

    Example::

        # Bad
        __all__ = ["foo", "bar"]  # F822 - bar is not defined

        def foo():
            pass

        # Good
        __all__ = ["foo"]

        def foo():
            pass
    """

    code: ClassVar[str] = "F822"
    message: ClassVar[str] = "undefined name '{name}' in __all__"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.ASSIGNMENT}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Check if this is an assignment to __all__
        left = node.child_by_field("left")
        if not left or not left.is_identifier or left.text != "__all__":
            return

        right = node.child_by_field("right")
        if not right:
            return

        # Get scope provider
        scope_prov: ScopeProvider = node.ctx.get_metadata(ScopeProvider)
        model = scope_prov.model
        if model.module_scope == NO_SCOPE:
            return
        module_scope = model.scope(model.module_scope)

        # Extract names from __all__
        names = self._extract_all_names(right)

        for name, name_node in names:
            # Check if name is defined in module scope
            if name not in module_scope.bindings and name not in BUILTINS:
                # Also check builtins
                yield self.diagnostic(
                    name_node,
                    self.message.format(name=name),
                )

    def _extract_all_names(self, node: Node) -> Iterator[tuple[str, Node]]:
        """Extract string names from __all__ list/tuple."""
        if node.type in ("list", "tuple"):
            for child in node.named_children:
                if child.type == "string":
                    # Remove quotes
                    text = child.text
                    if len(text) >= 2:
                        # Handle various quote styles
                        if text.startswith('"""') or text.startswith("'''"):
                            name = text[3:-3]
                        elif text.startswith('"') or text.startswith("'"):
                            name = text[1:-1]
                        else:
                            continue
                        yield (name, child)


class UndefinedLocal(Rule):
    """
    F823: Local variable referenced before assignment.

    Rationale: Using a local variable before it is assigned causes an
    ``UnboundLocalError`` at runtime.

    Example::

        # Bad
        def foo():
            print(x)  # F823 - x used before assignment
            x = 1

        # Good
        def foo():
            x = 1
            print(x)

    Optimized: Uses pre-computed undefined_locals from Rust SemanticModel.
    """

    code: ClassVar[str] = "F823"
    message: ClassVar[str] = "local variable '{name}' referenced before assignment"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.MODULE}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        """Check for uses before definitions using pre-computed list from Rust."""
        from rude.core.types import Location

        scope_prov: ScopeProvider = node.ctx.get_metadata(ScopeProvider)
        model = scope_prov.model

        # Iterate over pre-computed undefined locals
        for entry in model.undefined_locals:
            yield Diagnostic(
                code=self.code,
                message=self.message.format(name=entry.name),
                location=Location(line=entry.line, column=entry.column),
                severity=self.severity,
            )


NAME_RULES = [
    UndefinedName,
    UndefinedExport,
    UndefinedLocal,
]

__all__ = [
    "NAME_RULES",
    "UndefinedExport",
    "UndefinedLocal",
    "UndefinedName",
]
