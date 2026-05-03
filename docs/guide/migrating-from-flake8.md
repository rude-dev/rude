# Migrating from Flake8

This guide helps teams migrate from Flake8 to Rude. Since Rude uses the
same rule codes (F, E, W, C) as Flake8's core plugins, most configurations
translate directly.

## Why migrate?

- **17x faster** single-threaded on Django (901 files)
- **Native pyproject.toml** — no third-party plugin needed
- **Custom rules in Python** — without publishing a package
- **Semantic analysis** — scopes, bindings, qualified names via Rust engine
- **Autofix** — automatic fixes with import management

## Configuration mapping

### pyproject.toml

Flake8 reads `.flake8`, `setup.cfg`, or `tox.ini`. Rude reads
`pyproject.toml` natively.

**Flake8 (.flake8):**

```ini
[flake8]
max-line-length = 100
max-complexity = 12
select = E,W,F,C
ignore = E501,W503
per-file-ignores =
    tests/*:E501,E731
```

**Rude (pyproject.toml):**

```toml
[tool.rude]
select = ["E", "W", "F", "C"]
ignore = ["E501"]

[tool.rude.rules.E501]
max_line_length = 100

[tool.rude.rules.C901]
max_complexity = 12
```

### Key differences

| Flake8 option | Rude equivalent | Notes |
|---------------|-----------------|-------|
| `select` | `select` | Same semantics (prefix matching) |
| `ignore` / `extend-ignore` | `ignore` | Applied after `select` |
| `max-line-length` | `[tool.rude.rules.E501] max_line_length` or `--max-line-length` | Per-rule config |
| `max-complexity` | `[tool.rude.rules.C901] max_complexity` or `--max-complexity` | Per-rule config |
| `per-file-ignores` | `# noqa` or `should_check_file()` | No global per-file-ignores yet |
| `exclude` | `.gitignore` | Rude respects `.gitignore` and skips common directories automatically |

## Rule equivalences

Rude implements the same rule codes as Flake8's core plugins:

| Category | Flake8 plugin | Rude built-in | Coverage |
|----------|---------------|---------------|----------|
| Pyflakes | pyflakes | 46 rules (F4xx-F9xx) | ~97% (F405 not implemented) |
| Pycodestyle | pycodestyle | 51 E + 6 W rules | ~72% (see gaps below) |
| McCabe | mccabe | C901 | 100% |

Codes are identical — `F401` in Flake8 is `F401` in Rude, `E711` is `E711`,
and so on. Your existing `# noqa: F401` comments work unchanged.

### Not yet implemented

The following pycodestyle rules are not yet available in Rude. If your
project relies on them, you may see fewer diagnostics than Flake8.

**Continuation line indentation (14 rules):**
E112, E113, E114, E115, E116, E121, E122, E123, E124, E125, E126, E127,
E128, E129, E131, E133

These rules check indentation of continuation lines (multi-line
expressions, function arguments, etc.). They require stateful tracking
across logical lines and are planned for a future release.

**Other missing rules (7):**
- E252 -- missing whitespace around default parameter
- E502 -- redundant backslash
- E745 -- do not assign a lambda, use a def
- E901, E902 -- syntax/IO errors (partially covered by E999 and E000)
- W503, W504 -- line break before/after binary operator (deprecated in pycodestyle 2.11+)
- W505 -- doc line too long

**Not planned:**
- F405 -- requires cross-module star import tracking, complex infrastructure

Rude also provides **5 extra rules** beyond flake8: F542 (t-string
placeholders), F721/F722 (string annotations), F824 (unused
global/nonlocal), F842 (unused annotations).

## What's different

### Diagnostic count

Rude may report a slightly different number of diagnostics than Flake8 on
the same codebase. This is because:

- Some rules have subtly different edge-case behavior
- Rude uses tree-sitter (error-recovering) while Flake8 uses the stdlib AST
  (fails on syntax errors)
- Default thresholds may differ for configurable rules

On Django (901 files), Rude reports ~820 diagnostics (tier 2) vs Flake8's
~1,290. The difference comes mainly from pycodestyle whitespace rules where
implementations diverge on edge cases.

### Inline suppression

`# noqa` comments work the same way:

```python
x = 1  # noqa: E741
import os  # noqa: F401
x = 1  # noqa  (blanket — flagged by META002)
```

### No physical/logical line distinction

Flake8 distinguishes physical line checks (pycodestyle) from logical line
checks. Rude has two rule types:

- `Rule` — AST node checks (replaces Flake8 AST checkers)
- `LineRule` — raw text line checks (replaces physical + logical line checks)

## What's not supported

| Flake8 feature | Alternative |
|----------------|-------------|
| Import sorting (isort) | Use [Ruff](https://docs.astral.sh/ruff/) with `select = ["I"]` |
| `per-file-ignores` config | Use `# noqa` inline or `should_check_file()` in custom rules |
| Third-party Flake8 plugins | Check if Rude has the rule built-in; otherwise write a local rule |
| `--statistics` | Use `--format json` and post-process |
| `--benchmark` | Use `time rude check` or `benchmarks/bench_4way.py` |

## Step-by-step migration

1. **Install Rude alongside Flake8:**

   ```bash
   pip install rude
   ```

2. **Create `[tool.rude]` config** by translating your `.flake8` / `setup.cfg`
   settings using the mapping table above.

3. **Run both tools** and compare output:

   ```bash
   flake8 src/ > /tmp/flake8.txt
   rude check --format compact src/ > /tmp/rude.txt
   diff /tmp/flake8.txt /tmp/rude.txt
   ```

4. **Adjust configuration** until the diagnostics align to your satisfaction.
   Some differences are expected (see "What's different" above).

5. **Remove Flake8** from your dependencies once satisfied:

   ```bash
   pip uninstall flake8
   ```

6. **Add custom rules** for project-specific conventions that previously
   required Flake8 plugins. See the {doc}`custom-rules` guide.
