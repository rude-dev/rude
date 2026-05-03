# Quickstart

This guide covers everyday usage of the `rude` command-line tool.

## Checking files

Pass one or more files or directories to `rude check`:

```bash
rude check src/
```

Rude recursively finds all `.py` files, parses them with tree-sitter, and runs
every enabled rule. Output looks like this:

```text
src/utils.py:12:0: PAT008 eval() is a security risk; use ast.literal_eval() for literals
src/models.py:45:0: PAT004 Function 'process_data' is 87 lines (max 50)

Found 2 error(s) and 0 warning(s)
```

You can check multiple paths at once:

```bash
rude check src/ tests/ scripts/main.py
```

## Applying fixes

Many rules provide automatic fixes. Use `--fix` to apply them:

```bash
rude check --fix src/
```

Rude modifies files in place and reports what it fixed:

```text
Fixed 1 issue(s)
Found 0 error(s) and 0 warning(s)
```

Applied fixes are suppressed from the diagnostic output — only unfixed issues
are shown. If some fixes conflict (overlapping byte ranges), the conflicting
fixes are dropped and those diagnostics still appear in the output.

## Selecting and ignoring rules

### By code or prefix

Use `--select` to enable only specific rules or rule prefixes:

```bash
# Only pattern rules
rude check --select PAT src/

# Only specific rules
rude check --select PAT008,F841 src/

# Combine prefixes and codes
rude check --select PAT,F,META001 src/
```

Use `--ignore` to exclude rules from the active set:

```bash
# Everything except line-length
rude check --ignore E501 src/

# Exclude entire categories
rude check --ignore PAT,EX src/
```

Both options accept comma-separated values. Prefixes match any rule whose code
starts with the given string, so `F` matches `F401`, `F811`, `F841`, and so on.

## Parallel execution

By default (`--jobs=1`), Rude runs in a single Python process. Rust rayon
parallelizes file I/O, parsing, and semantic analysis inside the Rust
analyzer, and the GIL is released during per-file analysis so those phases
overlap with Python rule dispatch on the main thread. Measured speedup over a
pure single-threaded baseline is modest (~1.2x on an 8-core machine in our
benchmarks), because rule dispatch still runs serially on the main
interpreter.

For large codebases where Python rule execution becomes the bottleneck, use
`--jobs=N` to spawn multiple worker processes:

```bash
# 8 subprocesses, each with its own rayon pool + Python rules
rude check -j 8 src/
```

Each worker gets a balanced chunk of files (LPT scheduling) and runs the full
pipeline — rayon I/O, tree-sitter parse, semantic analysis, then Python rules —
independently. This bypasses the GIL for Python rule execution at the cost of
higher memory (roughly N × 70 MB for N workers).

:::{tip}
**When to use `--jobs`:** `--jobs=1` is the default and already uses rayon
inside the Rust analyzer; raise `N` for additional throughput on large
codebases. On small-to-medium projects (<1000 files) the default is usually
fast enough. On larger codebases with many Python rules enabled, `--jobs=N`
(where N is your CPU count) can meaningfully reduce wall time.
:::

:::{note}
Autofix mode (`--fix`) always runs sequentially because it writes files.
Unlike the normal check path, it also buffers each file's edits in memory
before writing, so the "streaming, flat-memory" story does not apply when
`--fix` is set.
:::

## Output formats

Rude supports three output formats via `--format`:

### Text (default)

Human-readable output with bold rule codes and a 🔧 marker on fixable
diagnostics (colors not shown here):

```bash
rude check src/
```

```text
src/utils.py:12:0: PAT008 eval() is a security risk; use ast.literal_eval() for literals 🔧
src/utils.py:45:0: F401 'os' imported but unused
```

### Compact

Plain text, one diagnostic per line, no colors or fixable markers. Suitable
for editor integration and `grep`:

```bash
rude check --format compact src/
```

```text
src/utils.py:12:0: PAT008 eval() is a security risk; use ast.literal_eval() for literals
src/utils.py:45:0: F401 'os' imported but unused
```

### JSON

Machine-readable output with one JSON object per line (JSON Lines format):

```bash
rude check --format json src/
```

```json
{"file": "src/utils.py", "line": 12, "column": 0, "code": "PAT008", "message": "eval() is a security risk; use ast.literal_eval() for literals", "severity": "warning", "fixable": true}
```

## Listing available rules

Use `rude list` to see all registered rules:

```bash
rude list
```

```text
Bugbear (B)
  B006       MutableDefaultArgument
  B007       UnusedLoopVariable
  ...

Pycodestyle errors (E)
  E101       MixedTabsAndSpaces
  E111       IndentationNotMultipleOfFour
  ...

Pyflakes (F)
  F401       UnusedImport
  F811       RedefinedWhileUnused
  ...
```

Add `--verbose` to include the first line of each rule's docstring:

```bash
rude list --verbose
```

```text
Patterns (PAT)
  PAT001     TooManyParameters         Functions with too many parameters.
  PAT002     TooManyBranches           Functions with too many branches (cyclomatic complexity).
  ...
```

## Quiet mode

Use `-q` (or `--quiet`) to suppress warnings and only print errors:

```bash
rude check -q src/
```

This is useful in CI pipelines where you want a non-zero exit code on errors
but do not want to see informational warnings.

## Early termination

### Fail fast

Stop on the first error:

```bash
rude check --fail-fast src/
```

### Max errors

Stop after a fixed number of errors:

```bash
rude check --max-errors 10 src/
```

Both options work in sequential and parallel modes.

## Exit codes

| Exit code | Meaning                         |
|-----------|----------------------------------|
| `0`       | No errors found                  |
| `1`       | One or more errors found, or no files/rules matched |

## Using a config file

By default, Rude searches upward from the current directory for a
`pyproject.toml` containing a `[tool.rude]` section. You can point to a
specific config file:

```bash
rude check --config path/to/pyproject.toml src/
```

See the {doc}`configuration` guide for the full list of configuration options.
