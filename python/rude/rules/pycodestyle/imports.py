"""
Import rules: E401, E402.

E401: multiple imports on one line
E402: module level import not at top of file
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic

if TYPE_CHECKING:
    from rude.core.node import Node


class MultipleImportsOnOneLine(Rule):
    """
    E401: Multiple imports on one line.

    Rationale: PEP 8 requires each import on its own line for clarity
    and cleaner diffs.

    Example::

        import os, sys      # E401

        import os           # OK
        import sys
    """

    code: ClassVar[str] = "E401"
    message: ClassVar[str] = "multiple imports on one line"
    node_types = {NodeType.IMPORT_STATEMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Quick-reject: can't have multiple imports with <=1 named child
        if node.named_child_count <= 1:
            return
        # Count dotted_name children (each is an import)
        import_count = 0
        for child in node.named_children:
            if child.type == "dotted_name":
                import_count += 1

        if import_count > 1:
            yield self.diagnostic(node)


class ModuleLevelImportNotAtTop(Rule):
    """
    E402: Module level import not at top of file.

    Imports should be at the top of the file, after any module docstring
    and comments, but before any other code.

    Example::

        x = 1
        import os           # E402

        import os           # OK
        x = 1
    """

    code: ClassVar[str] = "E402"
    message: ClassVar[str] = "module level import not at top of file"
    node_types = {NodeType.IMPORT_STATEMENT, NodeType.IMPORT_FROM_STATEMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Only check module-level imports
        if node.parent_type != "module":
            return

        # Get all module-level statements
        module = node.parent
        if module is None:
            return
        saw_code = False

        for child in module.named_children:
            if child == node:
                if saw_code:
                    yield self.diagnostic(node)
                return

            # Skip docstrings, comments, __future__ imports, and type checking blocks
            if self._is_allowed_before_imports(child):
                continue

            # Any other statement means we've seen code
            saw_code = True

    def _is_allowed_before_imports(self, node: Node) -> bool:
        """Check if node is allowed before imports."""
        # Comments
        if node.type == "comment":
            return True

        # Module docstring (expression_statement with string)
        if node.type == "expression_statement":
            children = node.named_children
            if children and children[0].type in ("string", "concatenated_string"):
                return True

        # Import statements (including __future__)
        if node.type in ("import_statement", "import_from_statement", "future_import_statement"):
            return True

        # __all__, __version__, etc. assignments
        if node.type == "assignment":
            left = node.child_by_field("left")
            if left and left.is_identifier:
                name = left.text
                if name.startswith("__") and name.endswith("__"):
                    return True

        # TYPE_CHECKING block
        if node.type == "if_statement":
            condition = node.child_by_field("condition")
            if condition and condition.text in ("TYPE_CHECKING", "typing.TYPE_CHECKING"):
                return True

        # try/except blocks (commonly used for conditional imports)
        return node.type == "try_statement"


IMPORT_RULES = [
    MultipleImportsOnOneLine,
    ModuleLevelImportNotAtTop,
]

__all__ = [
    "IMPORT_RULES",
    "ModuleLevelImportNotAtTop",
    "MultipleImportsOnOneLine",
]
