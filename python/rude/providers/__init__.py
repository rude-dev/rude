"""
Metadata providers for advanced analysis.

Providers compute additional information about the AST that rules
can use for more sophisticated checks. They are lazy-computed and cached.

Available providers:
- ParentProvider: Track parent of each node
- ScopeProvider: Scope and binding analysis (Rust-based, high-performance)
- QualifiedNameProvider: Resolve names to their qualified form
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, cast

# Re-export semantic types
from rude.providers.semantic import (
    NO_SCOPE,
    Binding,
    Scope,
    ScopeId,
    ScopeType,
    SemanticModel,
)

if TYPE_CHECKING:
    from rude.core.node import Node
    from rude.core.types import FileContext


# ─────────────────────────────────────────────────────────────────────────────
# Parent Provider
# ─────────────────────────────────────────────────────────────────────────────


class ParentProvider:
    """Provides parent node lookup."""

    __slots__ = ("_nodes", "_parents")

    def __init__(self) -> None:
        self._parents: dict[int, int] = {}
        self._nodes: dict[int, Node] = {}

    def compute(self, ctx: FileContext) -> Self:
        from rude.core.node import Node

        root = Node(ctx.tree.root_node, ctx)
        self._build(root, None)
        return self

    def _build(self, node: Node, parent: Node | None) -> None:
        self._nodes[node.raw.id] = node
        if parent:
            self._parents[node.raw.id] = parent.raw.id
        for child in node.children:
            self._build(child, node)

    def get(self, node: Node) -> Node | None:
        parent_id = self._parents.get(node.raw.id)
        if parent_id is None:
            return None
        return self._nodes.get(parent_id)


# ─────────────────────────────────────────────────────────────────────────────
# Scope Provider
# ─────────────────────────────────────────────────────────────────────────────


class ScopeProvider:
    """
    Provides scope and binding analysis using Rust-based analyzer.

    Uses a single call to analyze_source() which parses and traverses
    the AST entirely in Rust for maximum performance.

    Usage::

        sp = ctx.get_metadata(ScopeProvider)
        m = sp.model

        # Access module scope
        scope = m.scopes[m.module_scope]

        # Check unused bindings
        for name, bid in scope.bindings.items():
            binding = m.bindings[bid]
            if not binding.references:
                print(f"Unused: {name}")
    """

    __slots__ = ("model",)

    model: SemanticModel

    def __init__(self) -> None:
        self.model = cast("SemanticModel", None)  # uninitialized; set by compute() or from_model()

    def compute(self, ctx: FileContext) -> Self:
        from rude.providers.semantic import analyze_source

        self.model = analyze_source(tree=ctx.tree)
        return self

    @classmethod
    def from_model(cls, model: SemanticModel) -> Self:
        """Create a ScopeProvider with a pre-built SemanticModel."""
        inst = cls.__new__(cls)
        inst.model = model
        return inst


# ─────────────────────────────────────────────────────────────────────────────
# Qualified Name Provider
# ─────────────────────────────────────────────────────────────────────────────


class QualifiedNameProvider:
    """Resolves names to their qualified form based on imports."""

    __slots__ = ("_from_imports", "_imports")

    def __init__(self) -> None:
        self._imports: dict[str, str] = {}
        self._from_imports: dict[str, str] = {}

    def compute(self, ctx: FileContext) -> Self:
        from rude.core.node import Node

        root = Node(ctx.tree.root_node, ctx)
        self._collect_imports(root)
        return self

    def _collect_imports(self, node: Node) -> None:
        if node.type == "import_statement":
            for child in node.named_children:
                if child.type == "dotted_name":
                    parts = child.text.split(".")
                    self._imports[parts[0]] = parts[0]
                elif child.type == "aliased_import":
                    name = child.child_by_field("name")
                    alias = child.child_by_field("alias")
                    if name:
                        qname = name.text
                        local = alias.text if alias else qname.split(".")[0]
                        self._imports[local] = qname

        elif node.type == "import_from_statement":
            named_children = node.named_children
            module_node: Node | None = None
            module_name = ""

            for child in named_children:
                if child.type == "dotted_name":
                    module_node = child
                    module_name = child.text
                    break

            for child in named_children:
                if module_node and child.raw.id == module_node.raw.id:
                    continue
                if child.type == "dotted_name":
                    self._from_imports[child.text] = (
                        f"{module_name}.{child.text}" if module_name else child.text
                    )
                elif child.type == "aliased_import":
                    name = child.child_by_field("name")
                    alias = child.child_by_field("alias")
                    if name:
                        qname = f"{module_name}.{name.text}" if module_name else name.text
                        local = alias.text if alias else name.text
                        self._from_imports[local] = qname

        for child in node.children:
            self._collect_imports(child)

    def resolve(self, node: Node) -> str | None:
        if node.is_call:
            func = node.child_by_field("function")
            if not func:
                return None
            return self._resolve_expr(func)
        elif node.is_identifier:
            return self._resolve_name(node.text)
        elif node.is_attribute:
            return self._resolve_expr(node)
        return None

    def _resolve_name(self, name: str) -> str:
        if name in self._from_imports:
            return self._from_imports[name]
        if name in self._imports:
            return self._imports[name]
        return name

    def _resolve_expr(self, node: Node) -> str:
        if node.is_identifier:
            return self._resolve_name(node.text)
        elif node.is_attribute:
            obj = node.child_by_field("object")
            attr = node.child_by_field("attribute")
            if obj and attr:
                obj_resolved = self._resolve_expr(obj)
                return f"{obj_resolved}.{attr.text}"
        return node.text


__all__ = [
    "NO_SCOPE",
    "Binding",
    # Providers
    "ParentProvider",
    "QualifiedNameProvider",
    "Scope",
    "ScopeId",
    "ScopeProvider",
    # Semantic types
    "ScopeType",
]
