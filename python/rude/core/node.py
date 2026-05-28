"""
Ergonomic wrapper around tree-sitter nodes.

Provides a Pythonic API for rule authors with cached properties
and semantic helpers for Python constructs.
"""

from __future__ import annotations

import builtins
from collections.abc import Callable, Iterable, Iterator
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from rude._rust import NodeEntry, TSNode
    from rude.core.types import FileContext, Location, MetadataProviderT


class NodeLike(Protocol):
    """Protocol documenting the shared Node/NodeProxy interface.

    Both ``Node`` (full tree-sitter wrapper) and ``NodeProxy`` (lightweight
    batch proxy) satisfy this protocol.  Rule authors can type-hint
    ``NodeLike`` when they need to accept either transparently.
    """

    @property
    def type(self) -> str: ...
    @property
    def text(self) -> str: ...
    @property
    def line(self) -> int: ...
    @property
    def column(self) -> int: ...
    @property
    def start_byte(self) -> int: ...
    @property
    def end_byte(self) -> int: ...
    @property
    def children(self) -> list[Node]: ...
    @property
    def parent(self) -> Node | None: ...
    def child_by_field(self, name: str) -> Node | None: ...
    def get_metadata(self, provider_cls: builtins.type[MetadataProviderT]) -> MetadataProviderT: ...


class _NodeTypeMixin:
    """Mixin providing ``is_*`` type-check properties and ergonomic helpers.

    Both ``Node`` and ``NodeProxy`` inherit from this mixin.
    Concrete classes must expose: ``type``, ``text``, ``named_children``,
    ``child_by_field``.
    """

    # Declarations provided by concrete classes (Node, NodeProxy)
    @property
    def type(self) -> str:
        raise NotImplementedError

    @property
    def text(self) -> str:
        raise NotImplementedError

    @property
    def named_children(self) -> list[Node]:
        raise NotImplementedError

    def child_by_field(self, name: str) -> Node | None:
        raise NotImplementedError

    @property
    def is_call(self) -> bool:
        return self.type == "call"

    @property
    def is_function(self) -> bool:
        return self.type == "function_definition"

    @property
    def is_class(self) -> bool:
        return self.type == "class_definition"

    @property
    def is_import(self) -> bool:
        return self.type in ("import_statement", "import_from_statement", "future_import_statement")

    @property
    def is_import_from(self) -> bool:
        return self.type == "import_from_statement"

    @property
    def is_string(self) -> bool:
        return self.type == "string"

    @property
    def is_assignment(self) -> bool:
        return self.type in ("assignment", "augmented_assignment")

    @property
    def is_identifier(self) -> bool:
        return self.type == "identifier"

    @property
    def is_attribute(self) -> bool:
        return self.type == "attribute"

    @property
    def is_comment(self) -> bool:
        return self.type == "comment"

    @property
    def is_if(self) -> bool:
        return self.type == "if_statement"

    @property
    def is_for(self) -> bool:
        return self.type == "for_statement"

    @property
    def is_while(self) -> bool:
        return self.type == "while_statement"

    @property
    def is_try(self) -> bool:
        return self.type == "try_statement"

    @property
    def is_except(self) -> bool:
        return self.type == "except_clause"

    @property
    def is_return(self) -> bool:
        return self.type == "return_statement"

    @property
    def is_raise(self) -> bool:
        return self.type == "raise_statement"

    @property
    def is_assert(self) -> bool:
        return self.type == "assert_statement"

    @property
    def is_pass(self) -> bool:
        return self.type == "pass_statement"

    @property
    def is_with(self) -> bool:
        return self.type == "with_statement"

    @property
    def is_error(self) -> bool:
        """True if this node has type ``"ERROR"``.

        Note: this checks the type string only and does **not** account for
        ``is_missing`` nodes (parser-inserted recovery nodes).  On ``Node``,
        ``is_missing`` is available directly via the underlying TSNode; on
        ``NodeProxy`` it is not accessible without inflating to a full node,
        so the mixin deliberately omits that check to avoid unnecessary
        inflation.
        """
        return self.type == "ERROR"

    # ── Ergonomic helpers (duck-typed on concrete classes) ──

    def children_of_type(self, types: str | Iterable[str]) -> list[Node]:
        """Direct named children filtered by tree-sitter type.

        Accepts a single type or an iterable of types. Distinct from ``find()``
        (which recurses into descendants); this returns *direct* named children only.

        Note: triggers ``NodeProxy`` inflation (accesses ``named_children``).
        """
        wanted = {types} if isinstance(types, str) else set(types)
        return [c for c in self.named_children if c.type in wanted]

    def field_text(self, name: str) -> str | None:
        """Text of the field child, or ``None`` if the field is absent.

        Note: triggers ``NodeProxy`` inflation (accesses ``child_by_field``).
        """
        child = self.child_by_field(name)
        return child.text if child is not None else None

    def field_of_type(self, name: str, node_type: str) -> Node | None:
        """Field child iff its type matches ``node_type``, else ``None``.

        Note: triggers ``NodeProxy`` inflation (accesses ``child_by_field``).
        """
        child = self.child_by_field(name)
        return child if child is not None and child.type == node_type else None

    def is_operator(self, op: str | Iterable[str]) -> bool:
        """True if this node matches the given operator, by node type or text.

        Tree-sitter Python represents some operators as a node type (``==``,
        ``!=``, ...) and others only via text. This helper checks both transparently.
        """
        wanted = {op} if isinstance(op, str) else set(op)
        return self.type in wanted or self.text in wanted


class Node(_NodeTypeMixin):
    """
    Ergonomic wrapper around tree-sitter nodes.

    Example::

        if node.is_call and node.function_name == "eval":
            yield self.diagnostic(node)
    """

    __slots__ = ("_cache", "_ctx", "_node", "_type")

    def __init__(self, node: TSNode, ctx: FileContext) -> None:
        self._node = node
        self._ctx = ctx
        self._cache: dict[str, object] = {}
        self._type = node.type  # Cache type to avoid repeated FFI calls

    # ─────────────────────────────────────────────────────────────────────────
    # Type identity
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def type(self) -> str:
        return self._type

    @property
    def is_missing(self) -> bool:
        """True if the parser inserted this node to recover from a syntax error."""
        return self._node.is_missing

    @property
    def is_async(self) -> bool:
        first = self._node.children[0] if self._node.children else None
        return first is not None and first.type == "async"

    @property
    def parent_type(self) -> str | None:
        """Parent node type (matches NodeProxy lightweight property)."""
        p = self._node.parent
        return p.type if p else None

    @property
    def named_child_count(self) -> int:
        """Number of named children (matches NodeProxy lightweight property)."""
        return self._node.named_child_count

    # ─────────────────────────────────────────────────────────────────────────
    # Position & Text
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def text(self) -> str:
        return self._ctx.get_node_text(self._node)

    @property
    def line(self) -> int:
        return self._node.start_point[0] + 1

    @property
    def column(self) -> int:
        return self._node.start_point[1]

    @property
    def end_line(self) -> int:
        return self._node.end_point[0] + 1

    @property
    def end_column(self) -> int:
        return self._node.end_point[1]

    @property
    def start_byte(self) -> int:
        return self._node.start_byte

    @property
    def end_byte(self) -> int:
        return self._node.end_byte

    @property
    def location(self) -> Location:
        if "location" not in self._cache:
            from rude.core.types import Location

            self._cache["location"] = Location.from_ts_node(self._node)
        return cast("Location", self._cache["location"])

    # ─────────────────────────────────────────────────────────────────────────
    # Navigation
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def children(self) -> list[Node]:
        """All child nodes (cached)."""
        if "children" not in self._cache:
            self._cache["children"] = [Node(c, self._ctx) for c in self._node.children]
        return cast(list["Node"], self._cache["children"])

    @property
    def named_children(self) -> list[Node]:
        """Named child nodes only (cached)."""
        if "named_children" not in self._cache:
            self._cache["named_children"] = [Node(c, self._ctx) for c in self._node.named_children]
        return cast(list["Node"], self._cache["named_children"])

    @property
    def parent(self) -> Node | None:
        return Node(self._node.parent, self._ctx) if self._node.parent else None

    @property
    def next_sibling(self) -> Node | None:
        return Node(self._node.next_sibling, self._ctx) if self._node.next_sibling else None

    @property
    def prev_sibling(self) -> Node | None:
        return Node(self._node.prev_sibling, self._ctx) if self._node.prev_sibling else None

    def child_by_field(self, name: str) -> Node | None:
        child = self._node.child_by_field_name(name)
        return Node(child, self._ctx) if child else None

    def children_by_field(self, name: str) -> list[Node]:
        return [Node(c, self._ctx) for c in self._node.children_by_field_name(name)]

    def walk(self) -> Iterator[Node]:
        """Depth-first traversal of all descendants using TreeCursor.

        Uses tree-sitter's TreeCursor for efficient navigation without
        allocating Node wrappers for unvisited children. This reduces
        memory allocations significantly for large ASTs.
        """
        cursor = self._node.walk()

        reached_root = False
        while not reached_root:
            ts_node = cursor.node
            if ts_node is None:
                raise RuntimeError("Cannot walk a node with no underlying TSNode")
            yield Node(ts_node, self._ctx)

            if cursor.goto_first_child():
                continue
            if cursor.goto_next_sibling():
                continue

            # Backtrack up the tree
            while True:
                if not cursor.goto_parent():
                    reached_root = True
                    break
                if cursor.goto_next_sibling():
                    break

    def find(self, node_type: str) -> Iterator[Node]:
        """Find all descendants of a given type."""
        for node in self.walk():
            if node.type == node_type:
                yield node

    def find_first(self, node_type: str) -> Node | None:
        """Find first descendant of a given type."""
        return next(self.find(node_type), None)

    def find_where(self, predicate: Callable[[Node], bool]) -> Iterator[Node]:
        """Find all descendants matching a predicate."""
        for node in self.walk():
            if predicate(node):
                yield node

    def ancestor(self, node_type: str) -> Node | None:
        """Find nearest ancestor of a given type."""
        current = self.parent
        while current:
            if current.type == node_type:
                return current
            current = current.parent
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Semantic: Calls
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def function_name(self) -> str | None:
        """Simple function name: foo() -> 'foo', bar.baz() -> 'baz'"""
        if "function_name" not in self._cache:
            result = None
            if self.is_call:
                func = self.child_by_field("function")
                if func:
                    if func.is_identifier:
                        result = func.text
                    elif func.is_attribute:
                        attr = func.child_by_field("attribute")
                        result = attr.text if attr else None
            self._cache["function_name"] = result
        return cast("str | None", self._cache["function_name"])

    @property
    def full_call_name(self) -> str | None:
        """Full dotted name: os.path.join() -> 'os.path.join'"""
        if "full_call_name" not in self._cache:
            result = None
            if self.is_call:
                func = self.child_by_field("function")
                result = func.text if func else None
            self._cache["full_call_name"] = result
        return cast("str | None", self._cache["full_call_name"])

    @property
    def call_arguments(self) -> list[Node]:
        """Arguments of a call node."""
        if "call_arguments" not in self._cache:
            result: list[Node] = []
            if self.is_call:
                args = self.child_by_field("arguments")
                if args:
                    result = [c for c in args.named_children if c.type not in ("(", ")", ",")]
            self._cache["call_arguments"] = result
        return cast(list["Node"], self._cache["call_arguments"])

    # ─────────────────────────────────────────────────────────────────────────
    # Semantic: Definitions
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def name(self) -> str | None:
        """Name for function, class, or simple assignment."""
        if "name" not in self._cache:
            result = None
            if self.is_function or self.is_class:
                n = self.child_by_field("name")
                result = n.text if n else None
            elif self.is_assignment:
                left = self.child_by_field("left")
                if left and left.is_identifier:
                    result = left.text
            self._cache["name"] = result
        return cast("str | None", self._cache["name"])

    @property
    def decorators(self) -> list[Node]:
        """Decorators on function/class."""
        if "decorators" not in self._cache:
            result: list[Node] = []
            if self.is_function or self.is_class:
                for c in self._node.children:
                    if c.type == "decorator":
                        result.append(Node(c, self._ctx))
            self._cache["decorators"] = result
        return cast(list["Node"], self._cache["decorators"])

    @property
    def decorator_names(self) -> list[str]:
        """Decorator names as strings."""
        if "decorator_names" not in self._cache:
            names: list[str] = []
            for dec in self.decorators:
                for child in dec.children:
                    if child.is_identifier:
                        names.append(child.text)
                        break
                    if child.is_attribute:
                        names.append(child.text)
                        break
                    if child.is_call:
                        n = child.function_name
                        if n:
                            names.append(n)
                        break
            self._cache["decorator_names"] = names
        return cast(list[str], self._cache["decorator_names"])

    def has_decorator(self, name: str) -> bool:
        return name in self.decorator_names

    @property
    def parameters(self) -> list[Node]:
        """Function parameters."""
        if "parameters" not in self._cache:
            result: list[Node] = []
            if self.is_function:
                params = self.child_by_field("parameters")
                if params:
                    for c in params.named_children:
                        if c.type in (
                            "identifier",
                            "typed_parameter",
                            "default_parameter",
                            "typed_default_parameter",
                            "list_splat_pattern",
                            "dictionary_splat_pattern",
                        ):
                            result.append(c)
            self._cache["parameters"] = result
        return cast(list["Node"], self._cache["parameters"])

    @property
    def parameter_count(self) -> int:
        return len(self.parameters)

    @property
    def body(self) -> Node | None:
        """Body block for function/class/if/for/while."""
        return self.child_by_field("body")

    # ─────────────────────────────────────────────────────────────────────────
    # Semantic: Classes
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def bases(self) -> list[Node]:
        """Base classes for class definition."""
        if "bases" not in self._cache:
            result: list[Node] = []
            if self.is_class:
                superclasses = self.child_by_field("superclasses")
                if superclasses:
                    result = superclasses.named_children
            self._cache["bases"] = result
        return cast(list["Node"], self._cache["bases"])

    @property
    def base_names(self) -> list[str]:
        """Base class names as strings."""
        if "base_names" not in self._cache:
            self._cache["base_names"] = [b.text for b in self.bases]
        return cast(list[str], self._cache["base_names"])

    def inherits_from(self, name: str) -> bool:
        return name in self.base_names

    # ─────────────────────────────────────────────────────────────────────────
    # Semantic: Imports
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def import_module(self) -> str | None:
        """Module being imported."""
        if "import_module" not in self._cache:
            result = None
            if self.is_import_from:
                mod = self.child_by_field("module")
                result = mod.text if mod else None
            elif self.is_import:
                for c in self.named_children:
                    if c.type == "dotted_name":
                        result = c.text
                        break
                    elif c.type == "aliased_import":
                        n = c.child_by_field("name")
                        result = n.text if n else None
                        break
            self._cache["import_module"] = result
        return cast("str | None", self._cache["import_module"])

    # ─────────────────────────────────────────────────────────────────────────
    # Context & metadata
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def ctx(self) -> FileContext:
        return self._ctx

    def get_metadata(self, provider_cls: builtins.type[MetadataProviderT]) -> MetadataProviderT:
        """Shortcut for ctx.get_metadata()."""
        return self._ctx.get_metadata(provider_cls)

    @property
    def raw(self) -> TSNode:
        """Underlying tree-sitter node."""
        return self._node

    def __repr__(self) -> str:
        preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"Node({self.type!r}, {preview!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Node):
            return self._node.id == other._node.id
        if isinstance(other, NodeProxy):
            return (
                self._node.start_byte == other._entry.start_byte
                and self._node.end_byte == other._entry.end_byte
            )
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self._node.start_byte, self._node.end_byte))


class NodeProxy(_NodeTypeMixin):
    """
    Lightweight proxy that duck-types Node for batch dispatch.

    Wraps a frozen ``NodeEntry`` struct from Rust (3 slots vs 14),
    exposing fields as properties. Heavy properties (children, parent,
    etc.) inflate to a full Node on first access -- O(log depth).
    """

    __slots__ = ("_ctx", "_entry", "_node", "_text", "_type")

    def __init__(
        self,
        node_type: str,
        entry: NodeEntry,
        ctx: FileContext,
    ) -> None:
        self._type = node_type
        self._entry = entry
        self._ctx = ctx
        self._node: Node | None = None
        self._text: str | None = None

    def _inflate(self) -> Node:
        """Inflate to a full Node on demand."""
        if self._node is None:
            root = self._ctx.tree.root_node
            ts_node: TSNode | None
            sb = self._entry.start_byte
            eb = self._entry.end_byte
            if self._type == "module":
                ts_node = root
            else:
                ts_node = root.descendant_for_byte_range(sb, eb)
                while ts_node is not None and ts_node.type != self._type:
                    ts_node = ts_node.parent
                if ts_node is None:
                    ts_node = root.descendant_for_byte_range(sb, eb)
            if ts_node is None:
                raise RuntimeError(
                    f"Could not locate {self._type} node at byte range "
                    f"{sb}..{eb} in the syntax tree"
                )
            self._node = Node(ts_node, self._ctx)
        return self._node

    # ── Lightweight properties (no FFI) ──────────────────────────────────────

    @property
    def type(self) -> str:
        return self._type

    @property
    def text(self) -> str:
        if self._text is None:
            self._text = self._ctx.source[self._entry.start_byte : self._entry.end_byte].decode(
                "utf-8", errors="replace"
            )
        return self._text

    @property
    def line(self) -> int:
        return self._entry.start_row

    @property
    def column(self) -> int:
        return self._entry.start_col

    @property
    def start_byte(self) -> int:
        return self._entry.start_byte

    @property
    def end_byte(self) -> int:
        return self._entry.end_byte

    @property
    def ctx(self) -> FileContext:
        return self._ctx

    @property
    def location(self) -> Location:
        from rude.core.types import Location

        return Location(line=self._entry.start_row, column=self._entry.start_col)

    @property
    def is_async(self) -> bool:
        return self._entry.first_child_type == "async"

    # ── Heavy properties (inflate to Node) ───────────────────────────────────

    @property
    def children(self) -> list[Node]:
        return self._inflate().children

    @property
    def named_children(self) -> list[Node]:
        return self._inflate().named_children

    @property
    def parent(self) -> Node | None:
        return self._inflate().parent

    @property
    def next_sibling(self) -> Node | None:
        return self._inflate().next_sibling

    @property
    def prev_sibling(self) -> Node | None:
        return self._inflate().prev_sibling

    def child_by_field(self, name: str) -> Node | None:
        return self._inflate().child_by_field(name)

    def children_by_field(self, name: str) -> list[Node]:
        return self._inflate().children_by_field(name)

    def walk(self) -> Iterator[Node]:
        return self._inflate().walk()

    def find(self, node_type: str) -> Iterator[Node]:
        return self._inflate().find(node_type)

    def find_first(self, node_type: str) -> Node | None:
        return self._inflate().find_first(node_type)

    def find_where(self, predicate: Callable[[Node], bool]) -> Iterator[Node]:
        return self._inflate().find_where(predicate)

    def ancestor(self, node_type: str) -> Node | None:
        return self._inflate().ancestor(node_type)

    @property
    def raw(self) -> TSNode:
        return self._inflate().raw

    @property
    def end_line(self) -> int:
        return self._entry.end_row

    @property
    def end_column(self) -> int:
        return self._entry.end_col

    @property
    def parent_type(self) -> str | None:
        return self._entry.parent_type

    @property
    def named_child_count(self) -> int:
        return self._entry.named_child_count

    @property
    def child_count(self) -> int:
        return self._entry.child_count

    @property
    def first_child_type(self) -> str | None:
        return self._entry.first_child_type

    @property
    def last_child_type(self) -> str | None:
        return self._entry.last_child_type

    # Cached semantic properties (inflate)
    @property
    def name(self) -> str | None:
        return self._inflate().name

    @property
    def function_name(self) -> str | None:
        return self._inflate().function_name

    @property
    def full_call_name(self) -> str | None:
        return self._inflate().full_call_name

    @property
    def call_arguments(self) -> list[Node]:
        return self._inflate().call_arguments

    @property
    def decorators(self) -> list[Node]:
        return self._inflate().decorators

    @property
    def decorator_names(self) -> list[str]:
        return self._inflate().decorator_names

    def has_decorator(self, name: str) -> bool:
        return self._inflate().has_decorator(name)

    @property
    def parameters(self) -> list[Node]:
        return self._inflate().parameters

    @property
    def parameter_count(self) -> int:
        return self._inflate().parameter_count

    @property
    def body(self) -> Node | None:
        return self._inflate().body

    @property
    def bases(self) -> list[Node]:
        return self._inflate().bases

    @property
    def base_names(self) -> list[str]:
        return self._inflate().base_names

    def inherits_from(self, name: str) -> bool:
        return self._inflate().inherits_from(name)

    @property
    def import_module(self) -> str | None:
        return self._inflate().import_module

    def get_metadata(self, provider_cls: builtins.type[MetadataProviderT]) -> MetadataProviderT:
        return self._ctx.get_metadata(provider_cls)

    def __repr__(self) -> str:
        preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"NodeProxy({self._type!r}, {preview!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, NodeProxy):
            return (
                self._entry.start_byte == other._entry.start_byte
                and self._entry.end_byte == other._entry.end_byte
            )
        if isinstance(other, Node):
            return (
                self._entry.start_byte == other.start_byte
                and self._entry.end_byte == other.end_byte
            )
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self._entry.start_byte, self._entry.end_byte))


__all__ = ["Node", "NodeLike", "NodeProxy"]
