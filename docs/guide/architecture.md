# Architecture

How rude processes Python files, from invocation to diagnostics.

## Pipeline overview

```text
rude check src/
    |
    v
File discovery (Python)
    |  find_python_files() + .gitignore
    v
Rust batch pipeline (rayon)
    |  For each file in parallel (rayon thread pool):
    |    1. Read bytes (std::fs::read)
    |    2. Parse (tree-sitter, thread-local parser)
    |    3. Semantic analysis (scopes, bindings, imports)
    |    4. Group nodes by type
    |    5. Compute line metadata
    |
    |  Yields results through bounded channel (capacity 8)
    v
Python rule dispatch (main thread)
    |  For each file result:
    |    1. Build FileContext
    |    2. Dispatch AST rules by node type
    |    3. Dispatch line rules (fast path via LineInfo)
    |    4. Collect diagnostics
    v
Output (text, JSON, compact)
```

## Rust / Python boundary

The Rust extension (`rude._rust`) owns **parsing and analysis**. Python owns
**rules and orchestration**. The boundary is minimal:

```text
Python  ->  Rust                    Rust  ->  Python
-----------                         ----------------
parse_python(bytes)                 TSTree, TSNode
analyze_source(bytes|tree)          SemanticModel (frozen)
analyze_and_group(tree, types)      (SemanticModel, GroupsDict)
batch_analyze_iter(paths, types)    streaming iterator
```

All Rust types exposed to Python are `#[pyclass(frozen)]` -- immutable after
construction. No mutable state crosses the boundary.

## Key types

### SemanticModel

Built in Rust in a single AST traversal. Holds:

- **Scopes** -- module, function, class, comprehension (with parent chain)
- **Bindings** -- every name definition (imports, parameters, assignments)
- **References** -- every name use, linked to its binding
- **Pre-computed diagnostics** -- unused imports, unused variables, redefinitions,
  shadowed imports (computed in Rust, consumed by Python rules as frozen pyclasses)

### NodeEntry / NodeProxy

Rules receive `NodeProxy` -- a lightweight wrapper around `NodeEntry` (a Rust
struct with position, type, and parent info). The proxy inflates to a full
`Node` (with children, text, tree navigation) only when a rule accesses a
heavy property. This avoids FFI calls for rules that only check basic
properties like `type`, `line`, or `parent_type`.

### FileContext

The per-file context threaded through rule checking. Holds source bytes,
parsed tree, lazy-computed lines/text, noqa map, and metadata cache. Rules
access semantic data via `node.ctx.get_metadata(ScopeProvider)`.

## Parallelism model

### Default: single process, Rust parallelism

```text
+------------------------------------+
|  Single process                    |
|                                    |
|  Rust rayon (thread pool)          |
|    parse + analyze + group         |
|        |                           |
|        | bounded channel (8)       |
|        v                           |
|  Python (main thread, GIL)         |
|    rule dispatch                   |
+------------------------------------+
```

Rust releases the GIL during per-file analysis (`py.detach()` in
`analyze_source`); the streaming `batch_analyze_iter` path temporarily
re-acquires the GIL when building each result object before the next file is
yielded. The bounded channel keeps peak memory flat across a project -- for a
normal `rude check` run. `--fix` is an exception: it buffers each file's edits
in memory before writing, so the flat-memory guarantee does not hold there.

Measured speedup over a pure single-threaded baseline is modest (~1.2x on an
8-core machine): rule dispatch still runs serially on the main interpreter,
so overall throughput is capped by the Python side even when rayon saturates
the Rust side.

### `--jobs=N`: subprocess parallelism

```text
+------------------------------------------+
|  Worker 1    Worker 2    ...  Worker N    |
|  rayon       rayon            rayon       |
|  Python      Python           Python      |
+------------------------------------------+
```

Each worker gets a balanced chunk of files (LPT scheduling) and runs the
full pipeline. Rayon threads per worker scale to `cpu_count / N`.

## Plugin system

Rules are loaded from three sources:

1. **Built-in** -- `rude.rules.ALL_RULES` (pyflakes, pycodestyle, mccabe)
2. **Entry points** -- third-party packages registered under the `rude.plugins` group
3. **Local rules** -- Python files loaded via `importlib` from `local-rules` config

All three produce `RuleBase` subclasses. The linter treats them identically.

## Performance characteristics

| Operation | Where | Cost |
|-----------|-------|------|
| File I/O | Rust (rayon pool) | ~0.1ms/file |
| Parsing | Rust (thread-local parser) | ~1ms/file |
| Semantic analysis | Rust (single traversal) | ~2ms/file |
| Model conversion | Rust -> Python (GIL held) | ~1ms/file |
| Rule dispatch | Python (main thread) | ~5-20ms/file |
| Total per file | | ~10-25ms |

The bottleneck is Python rule dispatch -- as more rules run, the Python
fraction dominates (Amdahl's law). `--jobs=N` breaks through the GIL.
