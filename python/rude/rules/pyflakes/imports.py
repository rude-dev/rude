"""
Import-related rules.

F402: ImportShadowedByLoopVar - import shadowed by loop variable
F403: ImportStarUsed - star import used
F404: LateFutureImport - from __future__ import not at beginning of file
F406: ImportStarNotPermitted - star import outside module level
F407: FutureFeatureNotDefined - undefined __future__ feature
F811: RedefinedWhileUnused - redefinition of unused name
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Location, Severity
from rude.providers import ScopeProvider

if TYPE_CHECKING:
    from rude.core.node import Node


# Valid __future__ features as of Python 3.13
FUTURE_FEATURES = frozenset(
    {
        "nested_scopes",
        "generators",
        "division",
        "absolute_import",
        "with_statement",
        "print_function",
        "unicode_literals",
        "barry_as_FLUFL",
        "generator_stop",
        "annotations",
    }
)


class LateFutureImport(Rule):
    """
    F404: `from __future__` import not at the beginning of the file.

    Future imports must appear at the beginning of the file, after
    any module docstrings or comments, but before any other code.

    Example::

        x = 1
        from __future__ import annotations  # F404 - too late!

        from __future__ import annotations
        x = 1  # OK
    """

    code: ClassVar[str] = "F404"
    message: ClassVar[str] = "from __future__ imports must occur at the beginning of the file"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.IMPORT_FROM_STATEMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Check if this is a __future__ import
        module = node.child_by_field("module")
        if not module or module.text != "__future__":
            return

        # Check if it's at module level
        if node.parent_type != "module":
            # Not at module level
            yield self.diagnostic(node)
            return

        # Check what comes before this import
        parent = node.parent
        if parent is None:
            return
        for sibling in parent.children:
            if sibling.raw.id == node.raw.id:
                # Reached our import, all OK
                break

            # Skip comments, docstrings, and other future imports
            if sibling.type == "comment":
                continue
            if sibling.type == "expression_statement":
                child = sibling.named_children[0] if sibling.named_children else None
                if child and child.type == "string":
                    # Could be a docstring - only OK if it's the first statement
                    continue
            if sibling.type == "import_from_statement":
                # Check if it's another future import
                sib_module = sibling.child_by_field("module")
                if sib_module and sib_module.text == "__future__":
                    continue

            # Found a non-allowed statement before our future import
            yield self.diagnostic(node)
            return


class FutureFeatureNotDefined(Rule):
    """
    F407: Undefined name in __future__ import.

    Example::

        from __future__ import nonexistent_feature  # F407
        from __future__ import annotations  # OK
    """

    code: ClassVar[str] = "F407"
    message: ClassVar[str] = "future feature '{name}' is not defined"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.IMPORT_FROM_STATEMENT, NodeType.FUTURE_IMPORT_STATEMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Handle future_import_statement specially
        if node.type == "future_import_statement":
            for child in node.named_children:
                if child.type == "dotted_name":
                    # Get the actual identifier inside dotted_name
                    for subchild in child.named_children:
                        if subchild.type == "identifier":
                            name = subchild.text
                            if name not in FUTURE_FEATURES:
                                yield self.diagnostic(
                                    subchild,
                                    self.message.format(name=name),
                                )
            return

        # Check if this is a __future__ import (import_from_statement)
        module = node.child_by_field("module")
        if not module or module.text != "__future__":
            return

        # Check each imported name
        for child in node.named_children:
            if child == module:
                continue

            imported_name: str | None = None
            name_node: Node | None = None

            if child.type == "dotted_name":
                imported_name = child.text
                name_node = child
            elif child.type == "identifier":
                # Single identifier import
                imported_name = child.text
                name_node = child
            elif child.type == "aliased_import":
                name_field = child.child_by_field("name")
                if name_field:
                    imported_name = name_field.text
                    name_node = name_field

            if imported_name and imported_name not in FUTURE_FEATURES:
                yield self.diagnostic(
                    name_node or child,
                    self.message.format(name=imported_name),
                )


def _get_module_name(node: Node) -> str:
    """Get the module name from an import_from_statement."""
    for child in node.named_children:
        if child.type == "dotted_name":
            return child.text
        if child.type == "relative_import":
            for subchild in child.named_children:
                if subchild.type == "dotted_name":
                    return subchild.text
            return "."
    return "module"


class ImportStarNotPermitted(Rule):
    """
    F406: Star import (`from X import *`) used outside module level.

    Star imports are only allowed at the module level, not inside
    functions or classes.

    Example::

        from os import *  # OK - at module level

        def foo():
            from os import *  # F406 - not at module level
    """

    code: ClassVar[str] = "F406"
    message: ClassVar[str] = "'from {module} import *' only allowed at module level"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.IMPORT_FROM_STATEMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Check if this is a star import
        has_star = False
        for child in node.named_children:
            if child.type == "wildcard_import":
                has_star = True
                break

        if not has_star:
            return

        # Check if at module level
        if node.parent_type == "module":
            return  # OK - at module level

        # Not at module level
        module_name = _get_module_name(node)
        yield self.diagnostic(node, self.message.format(module=module_name))


class ImportStarUsed(Rule):
    """
    F403: `from X import *` used; unable to detect undefined names.

    Rationale: Star imports make it impossible to statically determine
    what names are defined, which can hide errors and cause name
    collisions.

    Example::

        # Bad
        from os import *  # F403 - star import used

        # Good
        from os import path, getcwd
    """

    code: ClassVar[str] = "F403"
    message: ClassVar[str] = "'from {module} import *' used; unable to detect undefined names"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.IMPORT_FROM_STATEMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Check if this is a star import
        has_star = False
        for child in node.named_children:
            if child.type == "wildcard_import":
                has_star = True
                break

        if not has_star:
            return

        # Only report at module level (F406 handles non-module level)
        if node.parent_type != "module":
            return

        module_name = _get_module_name(node)
        yield self.diagnostic(node, self.message.format(module=module_name))


class RedefinedWhileUnused(Rule):
    """
    F811: Redefinition of unused name from line N.

    Rationale: Redefining a name before it is used usually indicates
    a copy-paste error or a redundant import.

    Example::

        # Bad
        import os
        import os  # F811 - redefinition of unused 'os' from line 1

        # Good
        import os

    Optimized to use SemanticModel.redefinitions which tracks all
    binding redefinitions (assignment overwriting existing binding).
    Also uses model.bindings for import redefinitions.
    """

    code: ClassVar[str] = "F811"
    message: ClassVar[str] = "redefinition of unused '{name}' from line {line}"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.MODULE}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        scope_prov: ScopeProvider = node.ctx.get_metadata(ScopeProvider)
        model = scope_prov.model

        # Check redefinitions tracked by Rust analyzer.
        # The Rust side only records redefinitions where the OLD binding is an
        # import (matching flake8/pyflakes behavior: F811 only fires when an
        # import is overwritten by another import, def, class, or assignment).
        for redef in model.redefinitions:
            if not model.has_use_between(
                redef.name, redef.scope_id, redef.old_line, redef.new_line
            ):
                yield Diagnostic(
                    code=self.code,
                    message=self.message.format(name=redef.name, line=redef.old_line),
                    location=Location(line=redef.new_line, column=redef.new_column),
                    severity=self.severity,
                )


class ImportShadowedByLoopVar(Rule):
    """
    F402: Import shadowed by loop variable.

    Rationale: Reusing an imported name as a loop variable makes the
    import inaccessible after the loop, which is usually unintentional.

    Example::

        # Bad
        from os import path

        for path in paths:  # F402 - shadows import
            print(path)

        # Good
        from os import path

        for p in paths:
            print(p)

    Optimized: Uses pre-computed shadowed_imports from Rust SemanticModel.
    """

    code: ClassVar[str] = "F402"
    message: ClassVar[str] = "import '{name}' from line {line} shadowed by loop variable"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.MODULE}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        scope_prov: ScopeProvider = node.ctx.get_metadata(ScopeProvider)
        model = scope_prov.model

        # Iterate over pre-computed shadowed imports
        for shadow in model.shadowed_imports:
            yield Diagnostic(
                code=self.code,
                message=self.message.format(name=shadow.name, line=shadow.import_line),
                location=Location(line=shadow.loop_line, column=shadow.loop_column),
                severity=self.severity,
            )


IMPORT_RULES = [
    ImportShadowedByLoopVar,
    ImportStarUsed,
    LateFutureImport,
    FutureFeatureNotDefined,
    ImportStarNotPermitted,
    RedefinedWhileUnused,
    # ImportStarUsage (F405) is not included as it needs more infrastructure
]

__all__ = [
    "IMPORT_RULES",
    "FutureFeatureNotDefined",
    "ImportShadowedByLoopVar",
    "ImportStarNotPermitted",
    "ImportStarUsed",
    "LateFutureImport",
    "RedefinedWhileUnused",
]
