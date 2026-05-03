# Metadata providers

Metadata providers give rules access to semantic information that goes beyond
the raw AST. Instead of each rule re-analyzing the file independently,
providers compute shared data once and cache the results for the entire file.

Rude ships with three providers:

- {class}`~rude.providers.ParentProvider` -- look up a node's parent
- {class}`~rude.providers.ScopeProvider` -- scope and binding analysis
- {class}`~rude.providers.QualifiedNameProvider` -- resolve names to their fully qualified form

## How providers work

Providers are **lazy** and **cached**. The first time a rule (or the linter
engine) calls `ctx.get_metadata(ProviderClass)`, the provider's `compute()`
method runs and the result is stored. Subsequent calls return the cached
instance immediately.

To use a provider in a rule:

1. Declare it in `metadata_dependencies` on the rule class.
2. Call `ctx.get_metadata(ProviderClass)` inside `check()`.

```python
from rude import Diagnostic, Node, NodeType, Rule
from rude.providers import ScopeProvider
from typing import ClassVar, Iterator


class MyRule(Rule):
    code: ClassVar[str] = "ACME100"
    message: ClassVar[str] = "..."
    node_types = {NodeType.FUNCTION_DEFINITION}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        sp = node.get_metadata(ScopeProvider)
        model = sp.model
        # ... use model for semantic analysis
```

## ParentProvider

The `ParentProvider` builds a parent lookup table for every node in the AST.
This is useful when a rule needs to check the context in which a node appears.

### API

`provider.get(node)`
: Returns the parent `Node`, or `None` if the node is the root.

### Example: Flag `return` inside `finally`

```python
from rude import Diagnostic, Node, NodeType, Rule
from rude.providers import ParentProvider
from typing import ClassVar, Iterator


class NoReturnInFinally(Rule):
    """Flag return statements inside finally blocks."""

    code: ClassVar[str] = "ACME101"
    message: ClassVar[str] = "Do not use 'return' inside a finally block"
    node_types = {NodeType.RETURN_STATEMENT}
    metadata_dependencies: ClassVar[set[type]] = {ParentProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        pp = node.get_metadata(ParentProvider)
        current = node
        while current is not None:
            if current.type == "finally_clause":
                yield self.diagnostic(node)
                return
            if current.type == "function_definition":
                return  # Stop at function boundary
            current = pp.get(current)
```

## ScopeProvider

The `ScopeProvider` is the most powerful provider. It uses a Rust-based
analyzer to build a complete scope and binding model for the file in a single
pass. The result is a `SemanticModel` object with detailed information about
every variable, import, scope, and reference.

### API

`provider.model`
: The `SemanticModel` instance, or `None` if analysis failed.

### SemanticModel overview

The `SemanticModel` provides:

| Property / Method          | Description                                                     |
|----------------------------|-----------------------------------------------------------------|
| `scopes`                   | List of all `Scope` objects                                     |
| `bindings`                 | List of all `Binding` objects                                   |
| `imports()`                | List of all `ImportInfo` objects (method, not property)          |
| `module_scope`             | The module scope ID (`int`)                                     |
| `unused_variables`         | Tuples of `(name, line, col, start_byte, end_byte, scope_id)`  |
| `unused_imports`           | Tuples of `(name, line, col, start_byte, end_byte)`             |
| `scope_at(node)`           | Return the scope ID containing a node                           |
| `lookup(name, from_scope)` | Look up a binding ID by name in a scope chain                   |
| `has_context(start_byte, flag)` | Check if a position is inside a given context              |

### Scope object

Each `Scope` has:

| Property    | Description                                     |
|-------------|-------------------------------------------------|
| `type`      | Scope type: `MODULE`, `CLASS`, `FUNCTION`, or `COMPREHENSION` |
| `bindings`  | Dict mapping name strings to binding IDs         |
| `parent`    | Parent scope ID                                  |
| `children`  | List of child scope IDs                          |
| `globals`   | Set of names declared `global`                   |
| `nonlocals` | Set of names declared `nonlocal`                 |

### Binding object

Each `Binding` has:

| Property       | Description                                       |
|----------------|---------------------------------------------------|
| `name`         | The variable name                                 |
| `line`         | Line number (1-based)                             |
| `column`       | Column offset (0-based)                           |
| `scope`        | Scope ID this binding belongs to                  |
| `is_used`      | Whether this binding is referenced anywhere       |
| `references`   | List of tree-sitter node IDs that reference this binding |
| `is_import`    | True if defined by an import statement            |
| `is_parameter` | True if this is a function parameter              |

### Example: Detect unused variables (excluding `_` prefix)

```python
from rude import Diagnostic, Node, NodeType, Rule
from rude.providers import ScopeProvider
from rude.providers.semantic import SCOPE_FUNCTION
from typing import ClassVar, Iterator


class UnusedLocalVariable(Rule):
    """Flag local variables that are assigned but never read."""

    code: ClassVar[str] = "ACME110"
    message: ClassVar[str] = "Local variable '{name}' is assigned but never used"
    node_types = {NodeType.FUNCTION_DEFINITION}
    metadata_dependencies: ClassVar[set[type]] = {ScopeProvider}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        sp = node.get_metadata(ScopeProvider)
        model = sp.model
        if model is None:
            return

        # Find the function scope enclosing this node
        scope_id = model.scope_at(node)
        func_scope_id = model.enclosing_scope(scope_id, SCOPE_FUNCTION)
        if func_scope_id < 0:
            return
        scope = model.scope(func_scope_id)

        for name, bid in scope.bindings.items():
            # Skip private/underscore variables by convention
            if name.startswith("_"):
                continue

            binding = model.binding(bid)

            # Skip imports and parameters (separate rules handle those)
            if binding.is_import or binding.is_parameter:
                continue

            if not binding.is_used:
                yield self.diagnostic_at(
                    binding.line,
                    binding.column,
                    self.message.format(name=name),
                )
```

### Context flags

The `has_context()` method checks if a byte position is inside a given
construct (loop, function, class, etc.):

```python
from rude.providers.semantic import CTX_IN_LOOP, CTX_IN_FUNCTION

if model.has_context(node.start_byte, CTX_IN_LOOP):
    # Node is inside a loop
    ...

if model.has_context(node.start_byte, CTX_IN_FUNCTION):
    # Node is inside a function
    ...
```

Available flags:

| Flag                     | Meaning                          |
|--------------------------|----------------------------------|
| `CTX_IN_LOOP`           | Inside a `for` or `while` loop   |
| `CTX_IN_FUNCTION`       | Inside a function body           |
| `CTX_IN_CLASS`          | Inside a class body              |
| `CTX_IN_TRY`           | Inside a `try` block             |
| `CTX_IN_EXCEPT`        | Inside an `except` handler       |
| `CTX_IN_FINALLY`       | Inside a `finally` block         |
| `CTX_IN_WITH`          | Inside a `with` block            |
| `CTX_IN_LAMBDA`        | Inside a lambda expression       |
| `CTX_IN_COMPREHENSION` | Inside a comprehension           |

## QualifiedNameProvider

The `QualifiedNameProvider` resolves identifiers and attribute accesses to
their fully qualified form based on the file's import statements. This is
useful for rules that need to identify specific library calls regardless of
how they were imported.

### API

`provider.resolve(node)`
: Returns the qualified name as a string, or `None` if the name cannot be
  resolved. Works on call nodes, identifiers, and attribute accesses.

### Example: Flag deprecated API calls

```python
from rude import Diagnostic, Node, NodeType, Rule
from rude.providers import QualifiedNameProvider
from typing import ClassVar, Iterator


class NoDeprecatedAPIs(Rule):
    """Flag calls to deprecated standard library functions."""

    code: ClassVar[str] = "ACME120"
    message: ClassVar[str] = "'{name}' is deprecated; use '{replacement}'"
    node_types = {NodeType.CALL}
    metadata_dependencies: ClassVar[set[type]] = {QualifiedNameProvider}

    DEPRECATED = {
        "collections.MutableMapping": "collections.abc.MutableMapping",
        "collections.MutableSequence": "collections.abc.MutableSequence",
        "typing.Dict": "dict",
        "typing.List": "list",
        "typing.Optional": "X | None",
    }

    def check(self, node: Node) -> Iterator[Diagnostic]:
        qnp = node.get_metadata(QualifiedNameProvider)
        qname = qnp.resolve(node)

        if qname and qname in self.DEPRECATED:
            replacement = self.DEPRECATED[qname]
            yield self.diagnostic(
                node,
                self.message.format(name=qname, replacement=replacement),
            )
```

This rule correctly identifies `MutableMapping` regardless of whether the
user wrote:

```python
from collections import MutableMapping
MutableMapping()
```

or:

```python
import collections
collections.MutableMapping()
```

## Combining providers

A rule can depend on multiple providers:

```python
from rude import NodeType, Rule
from rude.providers import ScopeProvider, QualifiedNameProvider


class AdvancedRule(Rule):
    code = "ACME200"
    message = "..."
    node_types = {NodeType.CALL}
    metadata_dependencies = {ScopeProvider, QualifiedNameProvider}

    def check(self, node):
        sp = node.get_metadata(ScopeProvider)
        qnp = node.get_metadata(QualifiedNameProvider)
        # Use both providers together
        ...
```

Each provider is computed at most once per file, regardless of how many rules
request it.
