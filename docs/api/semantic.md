# Semantic Analysis API

The semantic analysis types (`SemanticModel`, `Scope`, `Binding`, `ImportInfo`,
`analyze_source`, `group_nodes`, the `SCOPE_*` and `CTX_*` constants, and the
related helpers) are re-exported as a stable public API from
`rude.providers.semantic`. The underlying implementation lives in a PyO3
extension at `rude._rust`, which is private -- do not import from it directly.
Always import from `rude.providers.semantic` in rule and plugin code.

The extension vendors tree-sitter internally (zero Python dependencies for
parsing), parses the AST entirely in Rust, and builds a complete semantic
model in a single pass. Since autodoc cannot introspect PyO3 classes, this
page documents the API manually based on the type stubs in
`python/rude/_rust.pyi`.

## Quick Start

```python
from rude.providers.semantic import analyze_source, SCOPE_MODULE, SCOPE_FUNCTION

model = analyze_source(b"""
import os
from pathlib import Path

def greet(name):
    unused = 42
    return f"Hello, {name}"

class App:
    pass
""")

# Inspect scopes
for scope in model.scopes:
    print(f"Scope type={scope.type}, bindings={list(scope.bindings.keys())}")

# Find unused imports (frozen pyclasses with named fields)
for entry in model.unused_imports:
    print(f"Unused import: {entry.name} at line {entry.line}")

# Find unused variables
for entry in model.unused_variables:
    print(f"Unused variable: {entry.name} at line {entry.line}, scope={entry.scope_id}")

# Retrieve all imports (note: imports() is a method, not a property)
for imp in model.imports():
    print(f"import {imp.module}.{imp.original_name} (line {imp.line})")

# Look up a binding by name from the module scope
binding_id = model.lookup("os")
if binding_id is not None:
    b = model.binding(binding_id)
    print(f"'{b.name}' is_import={b.is_import}")
```

---

## Module-Level Functions

### `parse_python`

```python
def parse_python(source: bytes) -> TSTree
```

Parse Python source bytes into a tree-sitter parse tree.

**Parameters:**

source
: Python source code as bytes.

**Returns:** A `TSTree` instance.

---

### `analyze_source`

```python
def analyze_source(
    source: bytes | None = None,
    *,
    tree: TSTree | None = None,
) -> SemanticModel
```

Parse Python source code and build a complete semantic model. This is the
primary entry point. You may pass raw `source` bytes (which will be parsed
internally), a pre-parsed `tree`, or both.

**Parameters:**

source
: Python source code as bytes. Optional if `tree` is provided.

tree
: A pre-parsed `TSTree`. Optional if `source` is provided.

**Returns:** A `SemanticModel` instance.

**Examples:**

```python
# From source bytes
model = analyze_source(b"import os\nprint(os.getcwd())")

# From a pre-parsed tree
tree = parse_python(b"import os")
model = analyze_source(tree=tree)

# Both (source is used for line-info computation, tree for analysis)
model = analyze_source(source=src, tree=tree)
```

---

### `group_nodes`

```python
def group_nodes(
    source: bytes,
    filter_types: list[str],
    *,
    tree: TSTree | None = None,
) -> dict[str, list[NodeEntry]]
```

Parse source and group AST nodes by type name. Each node is represented as
a `NodeEntry` struct with named fields (see [`NodeEntry`](#nodeentry) below).

**Parameters:**

source
: Python source bytes.

filter_types
: Node type names to include in groups (empty list = all types).

tree
: Optional pre-parsed tree to avoid re-parsing.

**Returns:** A dict mapping node type strings to lists of `NodeEntry` objects.

---

### `analyze_and_group`

```python
def analyze_and_group(
    tree: TSTree,
    filter_types: list[str],
) -> tuple[SemanticModel, dict[str, list[NodeEntry]]]
```

Analyze source and group nodes in a single AST traversal. Combines
`analyze_source` + `group_nodes` to avoid double traversal.

**Parameters:**

tree
: A pre-parsed `TSTree`.

filter_types
: Node type names to include in groups (empty list = all types).

**Returns:** A `(SemanticModel, groups_dict)` tuple.

---

### `batch_analyze_iter`

```python
def batch_analyze_iter(
    paths: list[str],
    filter_types: list[str],
) -> BatchAnalyzeIter
```

Streaming batch analyzer. Returns an iterator that yields
`(path, source_bytes, TSTree, SemanticModel, groups_dict)` tuples one at a
time as Rust finishes each file, where `groups_dict` maps node type strings
to lists of `NodeEntry` objects. This keeps memory bounded -- only one file's
data is materialized in Python at a time.

**Parameters:**

paths
: File paths to process.

filter_types
: Node type names to include in groups (empty list = all types).

**Returns:** A `BatchAnalyzeIter` iterator.

---

### `find_comment_start`

```python
def find_comment_start(line: str) -> int
```

Return the byte offset of the `#` character that starts a comment in a line,
or `-1` if the line has no comment.

**Parameters:**

line
: A single line of Python source code as a string.

**Returns:** Byte offset of `#`, or `-1`.

---

### `node_type_names`

```python
def node_type_names() -> list[str]
```

Return all tree-sitter node type names recognized by the vendored Python
grammar.

**Returns:** A list of node type name strings.

---

## `SemanticModel`

The central class holding all analysis results: scopes, bindings, imports,
and convenience methods for name resolution and context queries.

### Properties

#### Scope and Binding Access

`scopes` -> `list[Scope]`
: All scopes in the module, indexed by scope ID. The module scope is always
  at index 0.

`bindings` -> `list[Binding]`
: All bindings (variable definitions) in the module, indexed by binding ID.

`module_scope` -> `int`
: The scope ID of the top-level module scope.

`node_count` -> `int`
: Total number of tree-sitter nodes in the parsed AST.

#### Diagnostics

Each diagnostic property returns a list of frozen pyclass objects with
named fields. See the type stubs in `python/rude/_rust.pyi` for full
definitions.

`unused_variables` -> `list[UnusedBinding]`
: Bindings that are defined but never referenced (excluding imports,
  parameters, and names starting with `_`).
  Fields: `name`, `line`, `column`, `start_byte`, `end_byte`, `scope_id`.

`unused_imports` -> `list[UnusedBinding]`
: Import bindings that are never referenced.
  Fields: `name`, `line`, `column`, `start_byte`, `end_byte`, `scope_id`
  (`scope_id` is `-1` for module-level imports).

`unresolved` -> `list[UnresolvedRef]`
: Name uses that could not be resolved to any binding.
  Fields: `name`, `node_id`, `start_byte`, `line`, `column`, `scope_id`.

`annotation_only` -> `list[AnnotationRef]`
: Bindings that appear only in type annotations (never assigned or used
  at runtime).
  Fields: `name`, `node_id`, `start_byte`, `line`, `column`, `scope_id`.

`declarations` -> `list[Declaration]`
: All `global`/`nonlocal` declaration bindings.
  Fields: `name`, `node_id`, `start_byte`, `line`, `column`, `scope_id`, `is_global`.

`redefinitions` -> `list[Redefinition]`
: Bindings that redefine an earlier import in the same scope.
  Fields: `name`, `scope_id`, `new_line`, `new_column`, `old_line`.

`unused_annotations` -> `list[UnusedName]`
: Annotation-only bindings that are never used.
  Fields: `name`, `line`, `column`.

`unused_declarations` -> `list[UnusedDeclaration]`
: Declaration bindings that are never used.
  Fields: `name`, `line`, `column`, `is_global`.

`undefined_locals` -> `list[UnusedName]`
: Local names used before they are defined.
  Fields: `name`, `line`, `column`.

`shadowed_imports` -> `list[ShadowedImport]`
: Imports that are shadowed by a loop variable.
  Fields: `name`, `loop_line`, `loop_column`, `import_line`.

#### Line Metadata

`string_lines` -> `list[int]`
: 1-based line numbers that fall inside multi-line strings. Used by rules
  like E111 and E703 to skip lines inside strings.

`noqa_lines` -> `dict[int, list[str] | None]`
: Mapping of 1-based line number to noqa codes. A value of `None` means
  a bare `# noqa` (suppresses all diagnostics); a list of strings means
  `# noqa: E501,W291` etc.

`line_infos` -> `list[LineInfo]`
: Pre-computed per-line metadata as `LineInfo` structs with named fields
  (see [`LineInfo`](#lineinfo) below). Used internally by whitespace and
  indentation rules (`LineRule` subclasses with `uses_line_infos = True`)
  for performance.

### Methods

#### Scope Lookup

`scope(id: int) -> Scope`
: Return the `Scope` object for a given scope ID. This is the
  primary way to go from an integer scope ID to a `Scope` object.

`scope_at(node: object) -> int`
: Return the scope ID of the innermost scope containing the given
  tree-sitter node (uses the node's byte range).

`scope_at_node_id(node_id: int) -> int`
: Return the scope ID that owns the given tree-sitter node ID.

`scope_at_position(start_byte: int, end_byte: int) -> int`
: Return the scope ID of the innermost scope containing the given byte
  range.

`scope_for_position(byte_pos: int) -> int`
: Return the scope ID of the innermost scope containing a single byte
  position.

`scope_for(node: object) -> int`
: Return the scope ID for a tree-sitter node. Similar to `scope_at` but
  may use different resolution logic.

`scope_chain(scope_id: int) -> list[int]`
: Return the chain of scope IDs from the given scope up to the module
  scope (inclusive).

  ```python
  # Walk from an inner scope to the module scope
  chain = model.scope_chain(inner_scope_id)
  # chain[0] is the given scope, chain[-1] is the module scope
  ```

`enclosing_scope(scope_id: int, scope_type: int) -> int`
: Find the nearest enclosing scope of a given type. Returns the scope ID,
  or `NO_SCOPE` (-1) if none is found.

  ```python
  from rude.providers.semantic import SCOPE_FUNCTION, SCOPE_CLASS

  # Find enclosing function
  func_scope = model.enclosing_scope(scope_id, SCOPE_FUNCTION)

  # Find enclosing class
  cls_scope = model.enclosing_scope(scope_id, SCOPE_CLASS)
  ```

`is_in_function_scope(scope_id: int) -> bool`
: Check if the given scope is inside a function scope (i.e., has a
  function scope somewhere in its scope chain).

`is_in_class_scope(scope_id: int) -> bool`
: Check if the given scope is inside a class scope.

#### Binding Lookup

`binding(id: int) -> Binding`
: Return the `Binding` object for a given binding ID. This is the
  primary way to go from an integer binding ID to a `Binding` object.

`lookup(name: str, from_scope: int | None = None) -> int | None`
: Look up a binding by name, optionally starting from a specific scope.
  Returns a binding ID or `None` if the name is not found.

  ```python
  bid = model.lookup("os")
  if bid is not None:
      b = model.binding(bid)
      print(b.name, b.is_import)
  ```

`resolve_binding_from(name: str, use_byte: int, from_scope: int) -> int | None`
: Resolve a name at a specific byte position within a specific scope,
  walking up the scope chain. Returns a binding ID or `None`.

`visible_bindings(scope_id: int) -> list[tuple[str, int, int]]`
: Return all bindings visible in a scope (including inherited names from
  parent scopes). Each tuple is `(name, binding_id, scope_id)`.

`is_used(name: str, scope_id: int) -> bool`
: Check if a name has any uses within the given scope.

#### Import Queries

`imports() -> list[ImportInfo]`
: Return all import statements found in the module.

  ```{note}
  This is a **method**, not a property. You must call it with parentheses:
  `model.imports()`.
  ```

`future_imports() -> list[ImportInfo]`
: Return all `from __future__ import ...` statements.

  ```{note}
  This is a **method**. Call it as `model.future_imports()`.
  ```

`star_imports() -> list[ImportInfo]`
: Return all `from module import *` statements.

  ```{note}
  This is a **method**. Call it as `model.star_imports()`.
  ```

`import_info(binding_id: int) -> ImportInfo | None`
: Return the `ImportInfo` for a binding, or `None` if the binding
  is not an import.

  ```python
  bid = model.lookup("Path")
  if bid is not None:
      info = model.import_info(bid)
      if info:
          print(f"from {info.module} import {info.original_name}")
  ```

#### Use Tracking

`has_use_between(name: str, scope_id: int, start_line: int, end_line: int) -> bool`
: Check if a name is used between two line numbers (inclusive) within a
  scope.

`use_count_between(name: str, scope_id: int, start_byte: int, end_byte: int) -> int`
: Count the number of uses of a name within a byte range in a scope.

`use_lines(name: str, scope_id: int) -> list[int]`
: Return all line numbers where a name is used within a scope.

#### Context Queries

`has_context(start_byte: int, flag: int) -> bool`
: Check if a byte position has a specific ancestor context. Test against
  the `CTX_*` constants.

  ```python
  from rude.providers.semantic import CTX_IN_LOOP, CTX_IN_FUNCTION

  if model.has_context(offset, CTX_IN_LOOP):
      print("inside a loop")
  ```

`node_context(start_byte: int) -> tuple[int, int, int] | None`
: Return the full context tuple for a byte position, or `None` if the
  position is outside the AST.

`is_in_loop(start_byte: int) -> bool`
: Shorthand for `has_context(start_byte, CTX_IN_LOOP)`.

`is_in_function(start_byte: int) -> bool`
: Shorthand for `has_context(start_byte, CTX_IN_FUNCTION)`.

---

## `Scope`

Represents a lexical scope (module, class, function, or comprehension).

### Properties

`type` -> `int`
: Scope type as an integer. Compare against the scope type constants:
  `SCOPE_MODULE` (1), `SCOPE_CLASS` (2), `SCOPE_FUNCTION` (3),
  `SCOPE_COMPREHENSION` (4).

`type_` -> `int`
: Alias for `type` (useful when `type` conflicts with the builtin).

`node_id` -> `int`
: Tree-sitter node ID of the AST node that introduced this scope.

`parent` -> `int`
: Scope ID of the parent scope, or `-1` for the module scope.

`start_byte` -> `int`
: Start byte offset of the scope in the source.

`end_byte` -> `int`
: End byte offset of the scope in the source.

`bindings` -> `dict[str, int]`
: Mapping of name to binding ID for all names defined directly in
  this scope.

`globals` -> `set[str]`
: Names declared `global` in this scope.

`nonlocals` -> `set[str]`
: Names declared `nonlocal` in this scope.

`children` -> `list[int]`
: Scope IDs of direct child scopes.

`uses` -> `list[NameUse]`
: Name references within this scope. Each `NameUse` has fields:
  `name`, `node_id`, `start_byte`, `line`, `column`.

---

## `Binding`

Represents a single name binding (variable definition, import, parameter, etc.).

### Properties

`name` -> `str`
: The bound name.

`node_id` -> `int`
: Tree-sitter node ID where this binding was introduced.

`start_byte` -> `int`
: Start byte offset of the binding in the source.

`end_byte` -> `int`
: End byte offset of the binding in the source.

`line` -> `int`
: Line number (1-based) where the binding occurs.

`column` -> `int`
: Column offset (0-based) where the binding occurs.

`scope` -> `int`
: Scope ID of the scope that owns this binding.

`flags` -> `int`
: Bitmask of binding flags. Test against the flag constants:
  `FLAG_IMPORT`, `FLAG_PARAMETER`, `FLAG_GLOBAL`, `FLAG_NONLOCAL`,
  `FLAG_EXCEPTION`.

`valid_until_byte` -> `int | None`
: Byte offset where this binding goes out of scope (e.g., for exception
  handler variables). `None` if the binding is valid until the end of
  its scope.

`is_used` -> `bool`
: Whether this binding has any references.

`references` -> `list[int]`
: List of tree-sitter node IDs that reference this binding.

`is_import` -> `bool`
: Whether this binding was introduced by an import statement.

`is_parameter` -> `bool`
: Whether this binding is a function parameter.

`is_global` -> `bool`
: Whether this binding is declared `global`.

`is_nonlocal` -> `bool`
: Whether this binding is declared `nonlocal`.

`is_exception_handler` -> `bool`
: Whether this binding is an exception handler variable
  (e.g., `except ValueError as e`).

---

## `ImportInfo`

Metadata about a single import statement.

### Properties

`binding_id` -> `int`
: Binding ID that this import created. Use `model.binding(info.binding_id)`
  to get the full `Binding` object.

`module` -> `str`
: The module being imported (e.g., `"os.path"` for `import os.path`
  or `from os.path import join`).

`original_name` -> `str`
: The original name of the imported symbol before any aliasing
  (e.g., `"join"` for `from os.path import join as j`). For plain
  `import` statements, this is the module name.

`is_from_import` -> `bool`
: Whether this is a `from ... import ...` style import.

`is_star` -> `bool`
: Whether this is a `from ... import *` import.

`is_future` -> `bool`
: Whether this imports from `__future__`.

`is_aliased` -> `bool`
: Whether the import uses `as` (e.g., `import numpy as np`).

`is_relative` -> `bool`
: Whether this is a relative import (e.g., `from . import foo`).

`scope_id` -> `int`
: Scope ID where this import was found.

`line` -> `int`
: Line number (1-based) of the import statement.

`column` -> `int`
: Column offset (0-based) of the import statement.

---

(nodeentry)=
## `NodeEntry`

A frozen struct describing a single AST node, produced by `group_nodes`,
`analyze_and_group`, and `batch_analyze_iter`.
Carries enough positional data for `NodeProxy` to inflate to a full `Node`
on demand.

### Properties

`start_byte` -> `int`
: Byte offset of the first byte.

`end_byte` -> `int`
: Byte offset past the last byte.

`start_row` -> `int`
: 1-based start line number.

`start_col` -> `int`
: 0-based start column.

`end_row` -> `int`
: 1-based end line number.

`end_col` -> `int`
: 0-based end column.

`child_count` -> `int`
: Total number of children (named and anonymous).

`named_child_count` -> `int`
: Number of named children.

`parent_type` -> `str | None`
: Grammar type of the parent node, or `None` for the root.

`first_child_type` -> `str | None`
: Grammar type of the first child, or `None`.

`last_child_type` -> `str | None`
: Grammar type of the last child, or `None`.

---

(lineinfo)=
## `LineInfo`

A frozen struct holding pre-computed metrics for a single source line.
Produced by the Rust analyzer for fast line-rule evaluation without per-line
decoding or regex. Accessed via `SemanticModel.line_infos`.

### Properties

`leading_spaces` -> `int`
: Number of leading space characters.

`indent_len` -> `int`
: Visual indentation width (tabs count as N spaces).

`line_len` -> `int`
: Byte length of the line (excluding newline).

`trailing_ws` -> `int`
: Number of trailing whitespace bytes.

`comment_start` -> `int`
: Column of `#` starting a comment, or `-1`.

`indent_has_tab` -> `bool`
: True if the indentation contains at least one tab.

`indent_has_space` -> `bool`
: True if the indentation contains at least one space.

`is_blank` -> `bool`
: True if the line is blank (whitespace only).

`is_in_string` -> `bool`
: True if the line is inside a multi-line string literal.

`spaces_before_comment` -> `int`
: Spaces before `#`, or `-1` for block comments.

`char_after_hash` -> `int`
: ASCII byte of the character after `#`, or `0`.

`leading_hashes` -> `int`
: Number of leading `#` characters (for shebangs, etc.).

`style_flags` -> `int`
: Bitfield of style hints (see `LineRule.check_line_info` docs).

---

## Tree-Sitter Types

The semantic API exposes lightweight wrappers around tree-sitter's core
types. These are internal implementation details surfaced through the
private `rude._rust` extension; rules should operate on `SemanticModel`
and `Node` rather than these low-level handles.

### `TSTree`

A parsed syntax tree.

`root_node` -> `TSNode`
: The root node of the parse tree.

### `TSNode`

A single node in the syntax tree.

#### Properties

`type` -> `str`
: The grammar type name (e.g., `"function_definition"`, `"identifier"`).

`text` -> `bytes`
: The source text of this node.

`id` -> `int`
: Unique node ID within the tree.

`is_named` -> `bool`
: Whether this is a named node (as opposed to anonymous punctuation).

`is_missing` -> `bool`
: Whether this is a missing node inserted by error recovery.

`start_point` -> `tuple[int, int]`
: `(row, column)` of the start position.

`end_point` -> `tuple[int, int]`
: `(row, column)` of the end position.

`start_byte` -> `int`
: Start byte offset.

`end_byte` -> `int`
: End byte offset.

`child_count` -> `int`
: Total number of children (named and anonymous).

`named_child_count` -> `int`
: Number of named children.

`children` -> `list[TSNode]`
: All child nodes.

`named_children` -> `list[TSNode]`
: Named child nodes only.

`parent` -> `TSNode | None`
: The parent node, or `None` for the root.

`next_sibling` -> `TSNode | None`
: The next sibling node.

`prev_sibling` -> `TSNode | None`
: The previous sibling node.

#### Methods

`child_by_field_name(name: str) -> TSNode | None`
: Get a child node by its grammar field name.

`children_by_field_name(name: str) -> list[TSNode]`
: Get all children with a given grammar field name.

`walk() -> TSCursor`
: Create a cursor for efficient tree traversal.

`descendant_for_byte_range(start_byte: int, end_byte: int) -> TSNode | None`
: Find the smallest node that spans the given byte range.

### `TSCursor`

A cursor for efficient tree traversal.

`node` -> `TSNode`
: The current node.

`goto_first_child() -> bool`
: Move to the first child. Returns `False` if there are no children.

`goto_next_sibling() -> bool`
: Move to the next sibling. Returns `False` if there is no next sibling.

`goto_parent() -> bool`
: Move to the parent. Returns `False` if already at the root.

---

## Constants

### Scope Type Constants

These integer constants identify the kind of scope:

`NO_SCOPE` (= -1)
: Sentinel value indicating no scope.

`SCOPE_MODULE` (= 1)
: Module-level scope.

`SCOPE_CLASS` (= 2)
: Class body scope.

`SCOPE_FUNCTION` (= 3)
: Function body scope.

`SCOPE_COMPREHENSION` (= 4)
: Comprehension scope (list/dict/set comprehension or generator expression).

### Binding Flag Constants

Bitmask flags describing how a binding was introduced:

`FLAG_IMPORT` (= 1)
: Binding created by an import statement.

`FLAG_PARAMETER` (= 2)
: Binding is a function parameter.

`FLAG_GLOBAL` (= 4)
: Binding declared `global`.

`FLAG_NONLOCAL` (= 8)
: Binding declared `nonlocal`.

`FLAG_EXCEPTION` (= 16)
: Binding is an exception handler variable.

### Ancestor Context Flags

Bitmask flags for use with `SemanticModel.has_context()` and
`SemanticModel.node_context()`. These indicate what kind of AST
ancestors surround a given byte offset:

`CTX_IN_LOOP`
: Inside a `for` or `while` loop.

`CTX_IN_FUNCTION`
: Inside a function definition.

`CTX_IN_CLASS`
: Inside a class definition.

`CTX_IN_TRY`
: Inside a `try` block.

`CTX_IN_EXCEPT`
: Inside an `except` handler.

`CTX_IN_FINALLY`
: Inside a `finally` block.

`CTX_IN_WITH`
: Inside a `with` statement.

`CTX_IN_LAMBDA`
: Inside a `lambda` expression.

`CTX_IN_COMPREHENSION`
: Inside a list/dict/set comprehension or generator expression.

---

## Python Wrapper Types

The `rude.providers.semantic` module provides Python-side type aliases and
enumerations that complement the Rust extension:

`ScopeId`
: `NewType("ScopeId", int)` -- typed alias for scope indices.

`NO_SCOPE`
: `ScopeId(-1)` -- sentinel value for "no scope".

`ScopeType`
: `IntEnum` with members `MODULE`, `CLASS`, `FUNCTION`, `COMPREHENSION`.
  Maps to the same integer values as the Rust scope type constants.

The module also re-exports the `SCOPE_*` scope type constants and the
`CTX_*` ancestor context flags from the private `rude._rust` extension:

- `SCOPE_MODULE`
- `SCOPE_CLASS`
- `SCOPE_FUNCTION`
- `SCOPE_COMPREHENSION`
- `CTX_IN_LOOP`
- `CTX_IN_FUNCTION`
- `CTX_IN_CLASS`
- `CTX_IN_TRY`
- `CTX_IN_EXCEPT`
- `CTX_IN_FINALLY`
- `CTX_IN_WITH`
- `CTX_IN_LAMBDA`
- `CTX_IN_COMPREHENSION`
