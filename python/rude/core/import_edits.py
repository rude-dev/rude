"""Import insertion for autofixes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rude.core.node import Node
from rude.core.types import Edit

if TYPE_CHECKING:
    from rude.core.types import FileContext, Fix


class ImportInserter:
    """Computes edits to insert import statements."""

    def __init__(self, ctx: FileContext) -> None:
        self._ctx = ctx
        self._root = Node(ctx.tree.root_node, ctx)
        self._analyzed = False
        self._existing_imports: set[str] = set()
        self._existing_from_imports: set[tuple[str, str]] = set()
        self._insert_position: int = 0
        self._after_future: bool = False

    def _analyze(self) -> None:
        if self._analyzed:
            return
        self._analyzed = True

        first_import_pos: int | None = None
        last_future_end: int | None = None
        first_code_pos: int | None = None

        import_types = ("import_statement", "import_from_statement", "future_import_statement")

        for node in self._root.children:
            # Skip module docstring
            if node.type == "expression_statement" and first_import_pos is None:
                child = node.find_first("string")
                if child and first_code_pos is None:
                    continue

            # Track imports
            if node.type == "import_statement":
                if first_import_pos is None:
                    first_import_pos = node.start_byte
                self._parse_import(node)

            elif node.type == "import_from_statement":
                if first_import_pos is None:
                    first_import_pos = node.start_byte
                self._parse_from_import(node)

            elif node.type == "future_import_statement":
                if first_import_pos is None:
                    first_import_pos = node.start_byte
                last_future_end = node.end_byte

            elif node.type == "comment":
                continue

            elif first_code_pos is None and node.type not in import_types:
                first_code_pos = node.start_byte

        # Determine insert position
        if last_future_end is not None:
            self._insert_position = last_future_end
            self._after_future = True
        elif first_import_pos is not None:
            self._insert_position = first_import_pos
        elif first_code_pos is not None:
            self._insert_position = first_code_pos
        else:
            self._insert_position = 0

    def _parse_import(self, node: Node) -> None:
        """Parse 'import X, Y as Z' statement."""
        for child in node.named_children:
            if child.type == "dotted_name":
                self._existing_imports.add(child.text)
            elif child.type == "aliased_import":
                name = child.child_by_field("name")
                if name:
                    self._existing_imports.add(name.text)

    def _parse_from_import(self, node: Node) -> None:
        """Parse 'from X import Y, Z' statement.

        Tree-sitter Python represents ``import_from_statement`` as:
            from <dotted_name> import <dotted_name>, ...
        The "module" is NOT exposed as a named field; it is the first
        ``dotted_name`` child (before the ``import`` keyword).
        """
        # Find the module: first dotted_name child (before import keyword)
        module_node: Node | None = None
        past_import = False
        for child in node.children:
            if child.type == "import":
                past_import = True
                continue
            if not past_import and child.type == "dotted_name":
                module_node = child
                break

        if module_node is None:
            return
        module_name = module_node.text

        # Check for wildcard
        for child in node.children:
            if child.type == "wildcard_import":
                self._existing_imports.add(module_name)
                return

        # Parse imported names (dotted_name nodes after the import keyword)
        past_import = False
        for child in node.children:
            if child.type == "import":
                past_import = True
                continue
            if not past_import:
                continue
            if child.type == "dotted_name":
                self._existing_from_imports.add((module_name, child.text))
            elif child.type == "aliased_import":
                name = child.child_by_field("name")
                if name:
                    self._existing_from_imports.add((module_name, name.text))

    def has_import(self, module: str) -> bool:
        """Check if module is already imported."""
        self._analyze()
        return module in self._existing_imports

    def has_from_import(self, module: str, name: str) -> bool:
        """Check if 'from module import name' exists."""
        self._analyze()
        return (module, name) in self._existing_from_imports

    def get_import_edit(self, module: str) -> Edit | None:
        """Get edit to add 'import module', or None if already imported."""
        self._analyze()
        if self.has_import(module):
            return None

        # Check if any from-import covers this module
        for m, _ in self._existing_from_imports:
            if m == module:
                return None

        text = f"import {module}\n"
        if self._after_future:
            text = "\n" + text

        return Edit(self._insert_position, self._insert_position, text)

    def get_from_import_edit(self, module: str, name: str) -> Edit | None:
        """Get edit to add 'from module import name', or None if exists."""
        self._analyze()
        if self.has_from_import(module, name):
            return None

        text = f"from {module} import {name}\n"
        if self._after_future:
            text = "\n" + text

        return Edit(self._insert_position, self._insert_position, text)

    def get_merged_from_import_edit(self, module: str, names: list[str]) -> Edit | None:
        """Get edit for 'from module import name1, name2, ...'."""
        self._analyze()
        needed = sorted({n for n in names if not self.has_from_import(module, n)})
        if not needed:
            return None
        text = f"from {module} import {', '.join(needed)}\n"
        if self._after_future:
            text = "\n" + text
        return Edit(self._insert_position, self._insert_position, text)


def compute_merged_import_edits(ctx: FileContext, fixes: list[Fix]) -> list[Edit]:
    """Compute deduplicated import edits from surviving fixes."""
    inserter = ImportInserter(ctx)
    edits: list[Edit] = []

    all_imports: set[str] = set()
    for fix in fixes:
        all_imports.update(fix.imports_needed)
    for module in sorted(all_imports):
        edit = inserter.get_import_edit(module)
        if edit:
            edits.append(edit)

    from_imports: dict[str, list[str]] = {}
    for fix in fixes:
        for module, name in fix.imports_from_needed:
            from_imports.setdefault(module, []).append(name)
    for module in sorted(from_imports):
        edit = inserter.get_merged_from_import_edit(module, from_imports[module])
        if edit:
            edits.append(edit)

    return edits


__all__ = ["ImportInserter", "compute_merged_import_edits"]
