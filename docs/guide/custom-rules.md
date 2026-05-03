# Writing custom rules

Rude provides two base classes for writing lint rules:

- {class}`~rude.core.rule.Rule` -- inspect AST nodes (tree-sitter)
- {class}`~rude.core.rule.LineRule` -- inspect raw source lines

Both rule types share a common interface for configuration, diagnostics, and
file filtering. This guide walks through each type with complete examples.

## AST rules

AST rules are the most common type. They receive tree-sitter nodes that match
the `node_types` you declare and yield diagnostics when something is wrong.

### Minimal example

```python
from collections.abc import Iterator

from rude import Diagnostic, Node, NodeType, Rule


class NoGlobalVariables(Rule):
    """Flag module-level variable assignments."""

    code = "ACME001"
    message = "Avoid module-level mutable variables"
    node_types = {NodeType.EXPRESSION_STATEMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Only flag assignments at module level (column 0, not inside a class/function)
        if node.column == 0 and node.named_child_count > 0:
            child = node.named_children[0]
            if child.type == "assignment":
                yield self.diagnostic(node)
```

### Key attributes

`code`
: A unique identifier string for the rule (e.g., `"ACME001"`). Codes are
  used in `--select`, `--ignore`, `# noqa`, and output.

`message`
: The default diagnostic message shown to the user. Can be overridden per
  diagnostic in the `check()` method.

`node_types`
: A set of tree-sitter node type strings this rule wants to inspect. Rude
  only calls `check()` for nodes matching these types. Common types include
  `"call"`, `"function_definition"`, `"class_definition"`, `"import_statement"`,
  `"if_statement"`, `"expression_statement"`, and `"comment"`.

  Named constants are available in {mod}`rude.core.node_types` for IDE
  autocomplete and typo prevention (e.g., `CALL`, `FUNCTION_DEFINITION`).
  Invalid node types are rejected at registration time.

### Creating diagnostics

The `diagnostic()` method creates a diagnostic anchored to a node's location:

```python
def check(self, node: Node) -> Iterator[Diagnostic]:
    yield self.diagnostic(node)                          # default message
    yield self.diagnostic(node, "Custom message here")   # override message
```

For diagnostics at an arbitrary location (not tied to a specific node), use
`diagnostic_at()`:

```python
def check(self, node: Node) -> Iterator[Diagnostic]:
    yield self.diagnostic_at(
        line=node.line,
        column=node.column + 4,
        message="Problem starts here",
    )
```

### AST rule with autofix

Rules can suggest automatic fixes via the `Fix` class:

```python
from collections.abc import Iterator

from rude import Diagnostic, Fix, Node, NodeType, Rule


class ReplaceOsPathJoin(Rule):
    """Suggest pathlib over os.path.join."""

    code = "ACME002"
    message = "Use pathlib.Path instead of os.path.join()"
    node_types = {NodeType.CALL}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if node.full_call_name != "os.path.join":
            return

        args = node.call_arguments
        if not args:
            return

        # Build Path(a) / b / c replacement
        parts = [args[0].text] + [f" / {a.text}" for a in args[1:]]
        replacement = f"Path({''.join(parts)})" if len(args) == 1 else f"Path({args[0].text}){''.join(parts[1:])}"

        yield self.diagnostic(
            node,
            fix=Fix.replace(
                node,
                replacement,
                imports_from=[("pathlib", "Path")],
            ),
        )
```

### Fix API reference

The `Fix` class provides four factory methods:

`Fix.replace(node, new_text, *, description=None, imports=None, imports_from=None)`
: Replace the node's text with `new_text`. Optionally add top-level
  `import` statements (`imports`) or `from ... import` statements
  (`imports_from` as `(module, name)` tuples). The `description` is an
  optional human-readable string explaining the fix.

`Fix.delete(node, description=None)`
: Remove the node entirely.

`Fix.insert_before(node, text, *, description=None, imports=None)`
: Insert `text` immediately before the node.

`Fix.insert_after(node, text, *, description=None, imports=None)`
: Insert `text` immediately after the node.

`Fix.add_decorator(node, decorator, *, description=None, imports=None)`
: Add a `@decorator` line above a function or class definition, with
  correct indentation.

Example with import management:

```python
yield self.diagnostic(
    node,
    fix=Fix.replace(
        node,
        f"ensure_future({node.text})",
        imports_from=[("asyncio", "ensure_future")],
    ),
)
```

Rude automatically inserts the required `from asyncio import ensure_future`
statement at the top of the file if it does not already exist.

### How fixes are applied

When `--fix` is used, the linter collects all fixable diagnostics, applies
non-overlapping edits atomically, and returns a `FixResult`:

- `FixResult.source` — the fixed source code
- `FixResult.applied` — list of diagnostics whose fixes were applied
- `FixResult.dropped` — list of diagnostics whose fixes overlapped with
  higher-priority edits and were skipped

Import statements from all applied fixes are automatically merged. If multiple
fixes each need `from pathlib import Path`, only one import line is added.

Programmatic example:

```python
from rude import Linter, discover_rules

linter = Linter()
linter.register_all(discover_rules(select=["E711", "E713"]))

diagnostics, result = linter.fix_source(source)
if result:
    print(f"Fixed {len(result.applied)}, dropped {len(result.dropped)}")
    print(result.source)
```

## Line rules

Line rules inspect raw source text one line at a time. They are more
efficient than AST rules for simple text pattern matching.

```python
from collections.abc import Iterator

from rude import Diagnostic, FileContext, LineRule


class NoPrintStatements(LineRule):
    """Flag bare print() calls in production code."""

    code = "ACME010"
    message = "Remove print() statement"

    def should_check_file(self, ctx: FileContext) -> bool:
        return not ctx.is_test_file()

    def check_line(
        self,
        line: str,
        lineno: int,
        ctx: FileContext,
        *,
        comment_pos: int = -1,
    ) -> Iterator[Diagnostic]:
        # Only look in the code portion (before any comment)
        code_part = line[:comment_pos] if comment_pos >= 0 else line
        col = code_part.find("print(")
        if col >= 0:
            yield self.diagnostic_at(lineno, col)
```

### Parameters

`line`
: The full line as a decoded string, without the trailing newline.

`lineno`
: The 1-based line number.

`ctx`
: The {class}`~rude.core.types.FileContext` for accessing file-level
  information such as `ctx.path`, `ctx.is_test_file()`, or `ctx.text`.

`comment_pos`
: The column index of the `#` that starts a comment on this line, or `-1`
  if the line has no comment. This value is pre-computed by the linter and
  correctly ignores `#` characters inside string literals. Use
  `line[:comment_pos]` to get only the code portion.

## Conditional execution

All rule types support `should_check_file()` to skip files that are not
relevant:

```python
from rude import FileContext, NodeType


class ProductionOnlyRule(Rule):
    code = "ACME030"
    message = "..."
    node_types = {NodeType.CALL}

    def should_check_file(self, ctx: FileContext) -> bool:
        # Skip test files
        if ctx.is_test_file():
            return False
        # Only check files under src/
        if not ctx.is_in_path("src/"):
            return False
        return True

    def check(self, node):
        ...
```

The `FileContext` object provides these helpers:

- `ctx.is_test_file()` -- True if the path contains `/tests/`, `/test/`, or
  the filename starts with `test_` or ends with `_test.py`
- `ctx.is_in_path(*patterns)` -- True if any pattern appears in the file path
- `ctx.path` -- the `pathlib.Path` of the file being checked

## Configurable rules

Rules can accept per-rule options from `pyproject.toml` by overriding the
`configure()` method:

```python
from collections.abc import Iterator
from typing import Any

from rude import Diagnostic, Node, NodeType, Rule


class MaxReturnStatements(Rule):
    """Limit the number of return statements per function."""

    code = "ACME040"
    message = "Function has {count} return statements (max {max})"
    node_types = {NodeType.FUNCTION_DEFINITION}
    max_returns: int = 5

    def configure(self, options: dict[str, Any]) -> None:
        self.max_returns = options.get("max_returns", self.max_returns)

    def check(self, node: Node) -> Iterator[Diagnostic]:
        count = sum(1 for c in self._walk(node) if c.type == "return_statement")
        if count > self.max_returns:
            yield self.diagnostic(
                node,
                self.message.format(count=count, max=self.max_returns),
            )

    def _walk(self, node: Node) -> Iterator[Node]:
        for child in node.children:
            if child.type in ("function_definition", "lambda"):
                continue
            yield child
            yield from self._walk(child)
```

Configure it in `pyproject.toml`:

```toml
[tool.rude.rules.ACME040]
max_returns = 3
```

## Using metadata providers

Rules that need semantic information (scopes, bindings, qualified names) can
declare `metadata_dependencies` and access providers through the file context.
See the {doc}`metadata-providers` guide for a full walkthrough.

```python
from collections.abc import Iterator
from typing import ClassVar

from rude import Diagnostic, Node, NodeType, Rule, ScopeProvider
from rude.providers.semantic import SCOPE_FUNCTION


class NoShadowBuiltin(Rule):
    """Flag variables that shadow built-in names."""

    code = "ACME050"
    message = "'{name}' shadows a built-in"
    node_types = {NodeType.FUNCTION_DEFINITION}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    BUILTINS = frozenset({"list", "dict", "set", "type", "id", "input", "map", "filter", "open"})

    def check(self, node: Node) -> Iterator[Diagnostic]:
        model = node.get_metadata(ScopeProvider).model
        if model is None:
            return

        scope_id = model.scope_at(node)
        func_scope_id = model.enclosing_scope(scope_id, SCOPE_FUNCTION)
        if func_scope_id < 0:
            return
        scope = model.scope(func_scope_id)

        for name, bid in scope.bindings.items():
            if name in self.BUILTINS:
                binding = model.binding(bid)
                if binding and not binding.is_import:
                    yield self.diagnostic_at(
                        binding.line, binding.column,
                        self.message.format(name=name),
                    )
```

## Node API reference

The `Node` object passed to `check()` wraps a tree-sitter node with a
Pythonic API. All properties are cached for performance.

### Position and text

| Property | Type | Description |
|----------|------|-------------|
| `type` | `str` | Tree-sitter node type (e.g. `"call"`, `"function_definition"`) |
| `text` | `str` | Source text of the node |
| `line` | `int` | Start line (1-based) |
| `column` | `int` | Start column (0-based) |
| `end_line` | `int` | End line (1-based) |
| `end_column` | `int` | End column (0-based) |
| `start_byte` | `int` | Start byte offset in source |
| `end_byte` | `int` | End byte offset in source |

### Type checks

Convenience booleans to avoid string comparisons:

| Property | Equivalent to |
|----------|---------------|
| `is_call` | `type == "call"` |
| `is_function` | `type == "function_definition"` |
| `is_class` | `type == "class_definition"` |
| `is_import` | `type in ("import_statement", "import_from_statement", ...)` |
| `is_import_from` | `type == "import_from_statement"` |
| `is_string` | `type == "string"` |
| `is_assignment` | `type in ("assignment", "augmented_assignment")` |
| `is_identifier` | `type == "identifier"` |
| `is_attribute` | `type == "attribute"` |
| `is_comment` | `type == "comment"` |
| `is_if` | `type == "if_statement"` |
| `is_for` | `type == "for_statement"` |
| `is_while` | `type == "while_statement"` |
| `is_try` | `type == "try_statement"` |
| `is_except` | `type == "except_clause"` |
| `is_return` | `type == "return_statement"` |
| `is_raise` | `type == "raise_statement"` |
| `is_assert` | `type == "assert_statement"` |
| `is_pass` | `type == "pass_statement"` |
| `is_with` | `type == "with_statement"` |
| `is_async` | First child is `"async"` keyword |
| `is_error` | Syntax error node |

### Navigation

| Property / Method | Return type | Description |
|-------------------|-------------|-------------|
| `children` | `list[Node]` | All child nodes |
| `named_children` | `list[Node]` | Named children only (excludes punctuation) |
| `named_child_count` | `int` | Number of named children |
| `parent` | `Node \| None` | Parent node |
| `next_sibling` | `Node \| None` | Next sibling |
| `prev_sibling` | `Node \| None` | Previous sibling |
| `child_by_field(name)` | `Node \| None` | Child with a specific field name |
| `children_by_field(name)` | `list[Node]` | All children with a field name |
| `walk()` | `Iterator[Node]` | Depth-first traversal of all descendants |
| `find(node_type)` | `Iterator[Node]` | Find all descendants of a given type |
| `find_first(node_type)` | `Node \| None` | Find first descendant of a given type |
| `find_where(predicate)` | `Iterator[Node]` | Find descendants matching a predicate |
| `ancestor(node_type)` | `Node \| None` | Find nearest ancestor of a given type |

### Call semantics (for `call` nodes)

| Property | Type | Description |
|----------|------|-------------|
| `function_name` | `str \| None` | Simple name: `foo()` → `"foo"`, `bar.baz()` → `"baz"` |
| `full_call_name` | `str \| None` | Full dotted name: `os.path.join()` → `"os.path.join"` |
| `call_arguments` | `list[Node]` | Argument nodes of the call |

### Definition semantics (for functions, classes, assignments)

| Property / Method | Type | Description |
|-------------------|------|-------------|
| `name` | `str \| None` | Name of function, class, or assignment target |
| `decorators` | `list[Node]` | Decorator nodes |
| `decorator_names` | `list[str]` | Decorator names as strings |
| `has_decorator(name)` | `bool` | Check if a specific decorator is present |
| `parameters` | `list[Node]` | Function parameters |
| `parameter_count` | `int` | Number of parameters |
| `body` | `Node \| None` | Body block (function, class, if, for, while) |
| `bases` | `list[Node]` | Base class nodes (class definitions) |
| `base_names` | `list[str]` | Base class names as strings |
| `inherits_from(name)` | `bool` | Check if class inherits from a name |
| `import_module` | `str \| None` | Module name for import nodes |

### Context and metadata

| Property / Method | Type | Description |
|-------------------|------|-------------|
| `ctx` | `FileContext` | File context for this node |
| `get_metadata(ProviderClass)` | provider instance | Shortcut for `ctx.get_metadata()` |
| `raw` | `TSNode` | Underlying tree-sitter node |

## Node vs NodeProxy (implementation detail)

In batch mode (the default), `check()` receives a `NodeProxy` instead of a
full `Node`. You don't need to change anything in your rules — `NodeProxy`
supports the same API.

### Why it exists

Performance. `NodeProxy` stores pre-computed fields from Rust as a compact
struct (4 slots, same as Node), avoiding FFI overhead for common properties like
`type`, `start_byte`, `line`, `column`, `parent_type`, and `child_count`.

### Automatic inflation

Accessing heavyweight properties — `children`, `parent`,
`named_children`, `walk()` — transparently inflates the proxy to a full
`Node`. This is O(log depth) and cached; subsequent accesses are instant.

### Type checking

Both `Node` and `NodeProxy` support equality comparison with each other.
However, `isinstance(node, Node)` returns `False` for a `NodeProxy`.
Use duck-typing or check `hasattr` instead of `isinstance`.

### Pre-computed properties on NodeProxy

These properties are pre-computed from the Rust `NodeEntry` struct and
available without FFI overhead. They also exist on `Node` but require
a tree-sitter call:

| Property | Type | Description |
|----------|------|-------------|
| `parent_type` | `str \| None` | Type of the parent node |
| `child_count` | `int` | Number of children |
| `first_child_type` | `str \| None` | Type of the first child |
| `last_child_type` | `str \| None` | Type of the last child |

## Severity levels

Rules default to ERROR severity, which causes a non-zero exit code. For
informational rules that should not break CI, set the severity explicitly:

```python
from rude import Rule, Node, NodeType, Diagnostic, Severity
from collections.abc import Iterator


class TodoWithoutTicket(Rule):
    """Flag TODO comments without a ticket reference."""

    code = "ACME099"
    message = "TODO without ticket reference"
    severity = Severity.INFO
    node_types = {NodeType.COMMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if "TODO" in node.text and not any(p in node.text for p in ("JIRA-", "GH-", "#")):
            yield self.diagnostic(node)
```

Four levels are available:

| Level | Exit code | Shown with `--quiet` | Use for |
|-------|-----------|---------------------|---------|
| `Severity.ERROR` | 1 | yes | bugs, security, correctness |
| `Severity.WARNING` | 0 | no | style, best practices |
| `Severity.INFO` | 0 | no | suggestions, hygiene |
| `Severity.HINT` | 0 | no | minor hints, optional |

## Registering rules

To make your rules available to Rude, you have three options:

1. **Local rules** -- place them in a file and reference it in config:

   ```toml
   [tool.rude]
   local-rules = ["tools/lint_rules.py"]
   ```

2. **Plugin package** -- distribute as a Python package with an entry point.
   See the {doc}`plugin-development` guide.

3. **`RULES` list** -- export a `RULES` list from your module for explicit
   discovery:

   ```python
   # tools/lint_rules.py
   RULES = [NoGlobalVariables, ReplaceOsPathJoin, NoPrintStatements]
   ```

   If no `RULES` list is found, Rude auto-discovers all `Rule` subclasses
   in the module that have a `code` attribute.
