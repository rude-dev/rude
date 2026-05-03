# CLI Reference

Complete reference for all `rude` commands and options.

## `rude check`

Lint Python files and report diagnostics.

```bash
rude check [OPTIONS] PATH [PATH ...]
```

### Positional arguments

| Argument | Description |
|----------|-------------|
| `PATH` | One or more files or directories to lint. Directories are scanned recursively for `.py` files. |

### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--fix` | | Apply automatic fixes in place | off |
| `--select RULES` | | Enable only these rules or prefixes (comma-separated). Example: `PAT,F401` | all rules |
| `--ignore RULES` | | Exclude these rules or prefixes (comma-separated). Applied after `--select`. | none |
| `--format FORMAT` | | Output format: `text`, `compact`, or `json` | `text` |
| `--quiet` | `-q` | Suppress warnings, only show errors | off |
| `--config PATH` | | Path to `pyproject.toml` config file | auto-discovered |
| `--jobs N` | `-j` | Number of worker processes. `1` = single process with rayon parallelism. | `1` |
| `--fail-fast` | | Stop on first error | off |
| `--max-errors N` | | Stop after N errors | unlimited |
| `--max-line-length N` | | Override max line length for E501 | `79` |
| `--max-complexity N` | | Override max complexity for C901 | `10` |
| `--debug` | | Show full tracebacks on rule errors | off |

### Output formats

**text** (default) — Human-readable with bold rule codes and a `[fix]` marker
on fixable diagnostics:

```text
src/utils.py:12:0: PAT008 eval() is a security risk [fix]
```

**compact** — One diagnostic per line, no colors. Compatible with `errorformat`
in Vim and similar editors:

```text
src/utils.py:12:0: PAT008 eval() is a security risk
```

**json** — JSON Lines format, one object per line:

```json
{"file": "src/utils.py", "line": 12, "column": 0, "code": "PAT008", "message": "eval() is a security risk", "severity": "warning", "fixable": true}
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | No ERROR-severity diagnostics found |
| `1` | At least one ERROR-severity diagnostic found, or no files/rules matched |

WARNING, INFO, and HINT diagnostics do not affect the exit code. Use `--quiet`
to suppress them entirely and show only ERROR-severity diagnostics.

### Alias

`rude lint` is a permanent alias of `rude check`. Both commands behave
identically; use whichever you prefer.

## `rude list`

List all registered rules.

```bash
rude list [OPTIONS]
```

### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--verbose` | `-v` | Show rule descriptions (first line of docstring) | off |

### Example output

```text
Patterns (PAT)
  PAT001     TooManyParameters
  PAT002     TooManyBranches
  ...
```

## Global options

| Option | Short | Description |
|--------|-------|-------------|
| `--version` | `-V` | Print version and exit |
| `--help` | `-h` | Print help and exit |
