# ── Constants ──
NO_SCOPE: int
SCOPE_MODULE: int
SCOPE_CLASS: int
SCOPE_FUNCTION: int
SCOPE_COMPREHENSION: int
FLAG_IMPORT: int
FLAG_PARAMETER: int
FLAG_GLOBAL: int
FLAG_NONLOCAL: int
FLAG_EXCEPTION: int
CTX_IN_LOOP: int
CTX_IN_FUNCTION: int
CTX_IN_CLASS: int
CTX_IN_TRY: int
CTX_IN_EXCEPT: int
CTX_IN_FINALLY: int
CTX_IN_WITH: int
CTX_IN_LAMBDA: int
CTX_IN_COMPREHENSION: int

# ── Tree-sitter types ──
class TSTree:
    """Parsed tree-sitter syntax tree for a Python source file."""

    @property
    def root_node(self) -> TSNode:
        """The root ``module`` node of the syntax tree."""
        ...

class TSNode:
    """A single node in the tree-sitter concrete syntax tree."""

    @property
    def type(self) -> str:
        """Grammar type name (e.g. ``'function_definition'``, ``'identifier'``)."""
        ...
    @property
    def text(self) -> bytes:
        """Raw source bytes spanned by this node."""
        ...
    @property
    def id(self) -> int:
        """Unique numeric identifier for this node within its tree."""
        ...
    @property
    def is_named(self) -> bool:
        """True if this is a named (non-anonymous) grammar node."""
        ...
    @property
    def is_missing(self) -> bool:
        """True if the parser inserted this node to recover from a syntax error."""
        ...
    @property
    def start_point(self) -> tuple[int, int]:
        """``(row, column)`` of the first byte, both 0-based."""
        ...
    @property
    def end_point(self) -> tuple[int, int]:
        """``(row, column)`` of the byte after the last, both 0-based."""
        ...
    @property
    def start_byte(self) -> int:
        """Byte offset of the first byte."""
        ...
    @property
    def end_byte(self) -> int:
        """Byte offset past the last byte."""
        ...
    @property
    def child_count(self) -> int:
        """Total number of children (named and anonymous)."""
        ...
    @property
    def named_child_count(self) -> int:
        """Number of named children."""
        ...
    @property
    def children(self) -> list[TSNode]:
        """All child nodes (named and anonymous)."""
        ...
    @property
    def named_children(self) -> list[TSNode]:
        """Named child nodes only."""
        ...
    @property
    def parent(self) -> TSNode | None:
        """Parent node, or ``None`` for the root."""
        ...
    @property
    def next_sibling(self) -> TSNode | None:
        """Next sibling node, or ``None``."""
        ...
    @property
    def prev_sibling(self) -> TSNode | None:
        """Previous sibling node, or ``None``."""
        ...
    def child_by_field_name(self, name: str) -> TSNode | None:
        """Return the child with the given field name, or ``None``."""
        ...
    def children_by_field_name(self, name: str) -> list[TSNode]:
        """Return all children with the given field name."""
        ...
    def walk(self) -> TSCursor:
        """Create a ``TSCursor`` starting at this node for efficient traversal."""
        ...
    def descendant_for_byte_range(self, start_byte: int, end_byte: int) -> TSNode | None:
        """Return the smallest node spanning the given byte range."""
        ...

class TSCursor:
    """Stateful cursor for walking a tree-sitter tree without allocating Node wrappers."""

    @property
    def node(self) -> TSNode:
        """The node the cursor currently points to."""
        ...
    def goto_first_child(self) -> bool:
        """Move to the first child. Returns ``False`` if there are no children."""
        ...
    def goto_next_sibling(self) -> bool:
        """Move to the next sibling. Returns ``False`` if there is none."""
        ...
    def goto_parent(self) -> bool:
        """Move to the parent. Returns ``False`` if already at the root."""
        ...

# ── Node entry struct ──
class NodeEntry:
    """Lightweight, frozen struct describing a node for batch dispatch.

    Produced by ``group_nodes``.  Carries enough
    positional data for ``NodeProxy`` to inflate to a full ``Node`` on
    demand.
    """

    @property
    def start_byte(self) -> int:
        """Byte offset of the first byte."""
        ...
    @property
    def end_byte(self) -> int:
        """Byte offset past the last byte."""
        ...
    @property
    def start_row(self) -> int:
        """1-based start line number."""
        ...
    @property
    def start_col(self) -> int:
        """0-based start column."""
        ...
    @property
    def end_row(self) -> int:
        """1-based end line number."""
        ...
    @property
    def end_col(self) -> int:
        """0-based end column."""
        ...
    @property
    def parent_type(self) -> str | None:
        """Grammar type of the parent node, or ``None`` for the root."""
        ...
    @property
    def named_child_count(self) -> int:
        """Number of named children."""
        ...
    @property
    def child_count(self) -> int:
        """Total number of children (named and anonymous)."""
        ...
    @property
    def first_child_type(self) -> str | None:
        """Grammar type of the first child, or ``None``."""
        ...
    @property
    def last_child_type(self) -> str | None:
        """Grammar type of the last child, or ``None``."""
        ...

# ── Functions ──
from typing import TypeAlias

_GroupsDict: TypeAlias = dict[str, list[NodeEntry]]

def parse_python(source: bytes) -> TSTree:
    """Parse Python source bytes into a ``TSTree``."""
    ...

def analyze_source(source: bytes | None = None, *, tree: TSTree | None = None) -> SemanticModel:
    """Run semantic analysis, returning bindings, scopes, and import info."""
    ...

def analyze_and_group(tree: TSTree, filter_types: list[str]) -> tuple[SemanticModel, _GroupsDict]:
    """Analyze and group nodes in a single AST traversal."""
    ...

def group_nodes(
    source: bytes, filter_types: list[str], *, tree: TSTree | None = None
) -> _GroupsDict:
    """Group named nodes by type, filtered to the requested types."""
    ...

class BatchAnalyzeIter:
    """Streaming iterator for ``batch_analyze_iter``.

    Yields results one file at a time, allowing the caller to begin
    processing before all files are analyzed.
    """

    def __iter__(self) -> BatchAnalyzeIter: ...
    def __next__(self) -> tuple[str, bytes, TSTree, SemanticModel, _GroupsDict]: ...

def batch_analyze_iter(paths: list[str], filter_types: list[str]) -> BatchAnalyzeIter:
    """Analyze files in parallel via rayon, yielding results one at a time."""
    ...

def find_comment_start(line: str) -> int:
    """Return the column of ``#`` starting a comment, or ``-1``."""
    ...

def node_type_names() -> list[str]:
    """Return the list of all tree-sitter Python node type names."""
    ...

# ── Classes ──
class Binding:
    """A name binding (variable, import, parameter, etc.) within a scope.

    Tracks where a name was bound, its flags, usage references, and
    whether it is still live at a given point in the source.
    """

    @property
    def name(self) -> str:
        """The bound identifier name."""
        ...
    @property
    def node_id(self) -> int:
        """Tree-sitter node id of the binding site."""
        ...
    @property
    def start_byte(self) -> int:
        """Byte offset where the binding starts."""
        ...
    @property
    def end_byte(self) -> int:
        """Byte offset past the end of the binding."""
        ...
    @property
    def line(self) -> int:
        """1-based line number of the binding."""
        ...
    @property
    def column(self) -> int:
        """0-based column of the binding."""
        ...
    @property
    def scope(self) -> int:
        """Scope id this binding belongs to."""
        ...
    @property
    def flags(self) -> int:
        """Bitfield of ``FLAG_*`` constants (import, parameter, etc.)."""
        ...
    @property
    def valid_until_byte(self) -> int | None:
        """Byte offset where the binding goes out of scope, or ``None``."""
        ...
    @property
    def is_used(self) -> bool:
        """True if at least one reference to this binding was found."""
        ...
    @property
    def references(self) -> list[int]:
        """Tree-sitter node IDs of all use-sites referencing this binding."""
        ...
    @property
    def is_import(self) -> bool:
        """True if the binding was introduced by an import statement."""
        ...
    @property
    def is_parameter(self) -> bool:
        """True if the binding is a function parameter."""
        ...
    @property
    def is_global(self) -> bool:
        """True if the name is declared ``global``."""
        ...
    @property
    def is_nonlocal(self) -> bool:
        """True if the name is declared ``nonlocal``."""
        ...
    @property
    def is_exception_handler(self) -> bool:
        """True if the binding is an ``except ... as`` target."""
        ...

class Scope:
    """A lexical scope (module, class, function, or comprehension).

    Holds the bindings defined in this scope, declared globals/nonlocals,
    child scopes, and all name-use sites.
    """

    @property
    def type_(self) -> int:
        """Scope kind as a ``SCOPE_*`` constant (alias for ``type``)."""
        ...
    @property
    def type(self) -> int:
        """Scope kind as a ``SCOPE_*`` constant."""
        ...
    @property
    def node_id(self) -> int:
        """Tree-sitter node id of the scope-introducing node."""
        ...
    @property
    def parent(self) -> int:
        """Parent scope id, or ``NO_SCOPE``."""
        ...
    @property
    def start_byte(self) -> int:
        """Byte offset where the scope begins."""
        ...
    @property
    def end_byte(self) -> int:
        """Byte offset past the end of the scope."""
        ...
    @property
    def bindings(self) -> dict[str, int]:
        """Mapping of name -> binding id for names defined in this scope."""
        ...
    @property
    def globals(self) -> set[str]:
        """Names declared ``global`` in this scope."""
        ...
    @property
    def nonlocals(self) -> set[str]:
        """Names declared ``nonlocal`` in this scope."""
        ...
    @property
    def children(self) -> list[int]:
        """Ids of immediately nested child scopes."""
        ...
    @property
    def uses(self) -> list[NameUse]:
        """Name-use sites within this scope."""
        ...

class LineInfo:
    """Pre-computed metrics for a single source line.

    Produced by the Rust analyzer for fast line-rule evaluation
    without per-line decoding or regex.
    """

    @property
    def leading_spaces(self) -> int:
        """Number of leading space characters."""
        ...
    @property
    def indent_len(self) -> int:
        """Total number of leading whitespace characters (spaces and tabs each count as 1)."""
        ...
    @property
    def line_len(self) -> int:
        """Byte length of the line (excluding newline)."""
        ...
    @property
    def trailing_ws(self) -> int:
        """Number of trailing whitespace bytes."""
        ...
    @property
    def comment_start(self) -> int:
        """Column of ``#`` starting a comment, or ``-1``."""
        ...
    @property
    def indent_has_tab(self) -> bool:
        """True if the indentation contains at least one tab."""
        ...
    @property
    def indent_has_space(self) -> bool:
        """True if the indentation contains at least one space."""
        ...
    @property
    def is_blank(self) -> bool:
        """True if the line is blank (whitespace only)."""
        ...
    @property
    def is_in_string(self) -> bool:
        """True if the line is inside a multi-line string literal."""
        ...
    @property
    def spaces_before_comment(self) -> int:
        """Spaces before ``#``, or ``-1`` for block comments."""
        ...
    @property
    def char_after_hash(self) -> int:
        """ASCII byte of the character after ``#``, or ``0``."""
        ...
    @property
    def leading_hashes(self) -> int:
        """Number of leading ``#`` characters (for shebangs, etc.)."""
        ...
    @property
    def style_flags(self) -> int:
        """Bitfield of style hints (see ``LineRule.check_line_info`` docs)."""
        ...

class ImportInfo:
    """Metadata for a single import binding.

    Links the binding to its module, tracks aliasing, and records
    whether the import is relative, a star-import, or a future import.
    """

    @property
    def binding_id(self) -> int:
        """Id of the ``Binding`` this import created."""
        ...
    @property
    def module(self) -> str:
        """Dotted module path (e.g. ``'os.path'``)."""
        ...
    @property
    def original_name(self) -> str:
        """Name as written in the import (before any ``as`` alias)."""
        ...
    @property
    def is_star(self) -> bool:
        """True for ``from mod import *``."""
        ...
    @property
    def is_aliased(self) -> bool:
        """True when an ``as`` alias is used."""
        ...
    @property
    def is_future(self) -> bool:
        """True for ``from __future__ import ...``."""
        ...
    @property
    def is_relative(self) -> bool:
        """True for relative imports (leading dots)."""
        ...
    @property
    def is_from_import(self) -> bool:
        """True for ``from X import Y`` style imports."""
        ...
    @property
    def scope_id(self) -> int:
        """Scope id where the import appears."""
        ...
    @property
    def line(self) -> int:
        """1-based line number of the import statement."""
        ...
    @property
    def column(self) -> int:
        """0-based column of the import statement."""
        ...

class UnresolvedRef:
    """An unresolved name reference found during semantic analysis."""

    @property
    def name(self) -> str: ...
    @property
    def node_id(self) -> int: ...
    @property
    def start_byte(self) -> int: ...
    @property
    def line(self) -> int: ...
    @property
    def column(self) -> int: ...
    @property
    def scope_id(self) -> int: ...

class AnnotationRef:
    """An annotation-only name reference."""

    @property
    def name(self) -> str: ...
    @property
    def node_id(self) -> int: ...
    @property
    def start_byte(self) -> int: ...
    @property
    def line(self) -> int: ...
    @property
    def column(self) -> int: ...
    @property
    def scope_id(self) -> int: ...

class Declaration:
    """A global/nonlocal declaration."""

    @property
    def name(self) -> str: ...
    @property
    def node_id(self) -> int: ...
    @property
    def start_byte(self) -> int: ...
    @property
    def line(self) -> int: ...
    @property
    def column(self) -> int: ...
    @property
    def scope_id(self) -> int: ...
    @property
    def is_global(self) -> bool: ...

class Redefinition:
    """A redefinition of an unused import."""

    @property
    def name(self) -> str: ...
    @property
    def scope_id(self) -> int: ...
    @property
    def new_line(self) -> int: ...
    @property
    def new_column(self) -> int: ...
    @property
    def old_line(self) -> int: ...

class NameUse:
    """A name-use site within a scope."""

    @property
    def name(self) -> str: ...
    @property
    def node_id(self) -> int: ...
    @property
    def start_byte(self) -> int: ...
    @property
    def line(self) -> int: ...
    @property
    def column(self) -> int: ...

class UnusedBinding:
    """An unused variable or import binding."""

    @property
    def name(self) -> str: ...
    @property
    def line(self) -> int: ...
    @property
    def column(self) -> int: ...
    @property
    def start_byte(self) -> int: ...
    @property
    def end_byte(self) -> int: ...
    @property
    def scope_id(self) -> int: ...

class UnusedName:
    """An unused name for annotations (F842) and undefined locals (F823)."""

    @property
    def name(self) -> str: ...
    @property
    def line(self) -> int: ...
    @property
    def column(self) -> int: ...

class UnusedDeclaration:
    """An unused global/nonlocal declaration."""

    @property
    def name(self) -> str: ...
    @property
    def line(self) -> int: ...
    @property
    def column(self) -> int: ...
    @property
    def is_global(self) -> bool: ...

class ShadowedImport:
    """An import shadowed by a loop variable."""

    @property
    def name(self) -> str: ...
    @property
    def loop_line(self) -> int: ...
    @property
    def loop_column(self) -> int: ...
    @property
    def import_line(self) -> int: ...

class SemanticModel:
    """Result of semantic analysis on a Python source file.

    Provides access to scopes, bindings, imports, and derived queries
    such as unused variables, redefinitions, and scope lookups.
    All scope and binding ids are indices into the ``scopes`` and
    ``bindings`` lists respectively.
    """

    @property
    def scopes(self) -> list[Scope]:
        """All scopes in definition order. Index 0 is the module scope."""
        ...
    @property
    def bindings(self) -> list[Binding]:
        """All bindings in definition order."""
        ...
    def scope(self, id: int) -> Scope:
        """Return the scope with the given id."""
        ...
    def binding(self, id: int) -> Binding:
        """Return the binding with the given id."""
        ...
    @property
    def module_scope(self) -> int:
        """Id of the module-level scope (always 0)."""
        ...
    @property
    def unresolved(self) -> list[UnresolvedRef]:
        """Unresolved name references."""
        ...
    @property
    def annotation_only(self) -> list[AnnotationRef]:
        """Annotation-only names."""
        ...
    @property
    def declarations(self) -> list[Declaration]:
        """Global/nonlocal declarations."""
        ...
    @property
    def redefinitions(self) -> list[Redefinition]:
        """Import redefinitions."""
        ...
    @property
    def unused_variables(self) -> list[UnusedBinding]:
        """Unused variable bindings."""
        ...
    @property
    def unused_imports(self) -> list[UnusedBinding]:
        """Unused import bindings."""
        ...
    @property
    def unused_annotations(self) -> list[UnusedName]:
        """Unused annotation-only bindings."""
        ...
    @property
    def unused_declarations(self) -> list[UnusedDeclaration]:
        """Unused declarations."""
        ...
    @property
    def undefined_locals(self) -> list[UnusedName]:
        """Uses of names not defined in their scope."""
        ...
    @property
    def shadowed_imports(self) -> list[ShadowedImport]:
        """Imports shadowed by later bindings."""
        ...
    @property
    def node_count(self) -> int:
        """Total number of AST nodes in the parsed tree."""
        ...
    @property
    def string_lines(self) -> list[int]:
        """1-based line numbers that are inside multi-line string literals."""
        ...
    @property
    def noqa_lines(self) -> dict[int, list[str] | None]:
        """Mapping of 1-based line -> suppressed codes (``None`` = blanket noqa)."""
        ...
    @property
    def line_infos(self) -> list[LineInfo]:
        """Pre-computed ``LineInfo`` for every source line."""
        ...
    def lookup(self, name: str, from_scope: int | None = None) -> int | None:
        """Look up a name starting from the given scope. Returns binding id or ``None``."""
        ...
    def resolve_binding_from(self, name: str, use_byte: int, from_scope: int) -> int | None:
        """Resolve a name use at a specific byte offset. Returns binding id or ``None``."""
        ...
    def is_used(self, name: str, scope_id: int) -> bool:
        """Check whether a name is used in the given scope."""
        ...
    def scope_at_node_id(self, node_id: int) -> int:
        """Return the scope id for a tree-sitter node id."""
        ...
    def scope_at_position(self, start_byte: int, end_byte: int) -> int:
        """Return the innermost scope spanning the given byte range."""
        ...
    def scope_for_position(self, byte_pos: int) -> int:
        """Return the innermost scope containing the given byte offset."""
        ...
    def scope_for(self, node: object) -> int:
        """Return the scope id that *contains* the given node."""
        ...
    def scope_at(self, node: object) -> int:
        """Return the scope id that the given node *introduces* (for def/class)."""
        ...
    def scope_chain(self, scope_id: int) -> list[int]:
        """Return the chain of scope ids from the given scope up to the module."""
        ...
    def is_in_function_scope(self, scope_id: int) -> bool:
        """True if the scope or any ancestor is a function scope."""
        ...
    def is_in_class_scope(self, scope_id: int) -> bool:
        """True if the scope or any ancestor is a class scope."""
        ...
    def enclosing_scope(self, scope_id: int, scope_type: int) -> int:
        """Return the nearest enclosing scope of the given type."""
        ...
    def visible_bindings(self, scope_id: int) -> list[tuple[str, int, int]]:
        """Bindings visible from the given scope: ``(name, binding_id, scope_id)``."""
        ...
    def has_use_between(self, name: str, scope_id: int, start_line: int, end_line: int) -> bool:
        """Check for any use of a name between two lines."""
        ...
    def use_count_between(self, name: str, scope_id: int, start_byte: int, end_byte: int) -> int:
        """Count uses of a name in the given byte range."""
        ...
    def use_lines(self, name: str, scope_id: int) -> list[int]:
        """Return all 1-based line numbers where a name is used in a scope."""
        ...
    def is_in_loop(self, start_byte: int) -> bool:
        """True if the byte offset is inside a loop body."""
        ...
    def is_in_function(self, start_byte: int) -> bool:
        """True if the byte offset is inside a function body."""
        ...
    def has_context(self, start_byte: int, flag: int) -> bool:
        """Check a ``CTX_*`` flag at the given byte offset."""
        ...
    def node_context(self, start_byte: int) -> tuple[int, int, int] | None:
        """Return ``(flags, loop_depth, function_depth)`` at the given byte offset."""
        ...
    def imports(self) -> list[ImportInfo]:
        """All imports found in the source."""
        ...
    def import_info(self, binding_id: int) -> ImportInfo | None:
        """Return ``ImportInfo`` for a binding, or ``None`` if it is not an import."""
        ...
    def star_imports(self) -> list[ImportInfo]:
        """All ``from X import *`` imports."""
        ...
    def future_imports(self) -> list[ImportInfo]:
        """All ``from __future__ import ...`` imports."""
        ...
