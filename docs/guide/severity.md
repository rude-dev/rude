# Severity levels

Rude assigns a severity to every diagnostic. Severity controls two things:
whether the diagnostic causes a non-zero exit code, and whether `--quiet`
suppresses it.

## Overview

Rude has four severity levels. The default is **ERROR**, which means any
diagnostic causes `exit 1` -- matching the behavior of Ruff and Flake8 where
every finding is fatal. Rules that want non-blocking behavior must explicitly
opt in to a lower severity.

## The four levels

| Level | Exit code | Shown with `--quiet`? | Intended use |
|---|---|---|---|
| `ERROR` | 1 | yes | Bugs, undefined names, syntax errors, style violations (default) |
| `WARNING` | 0 | no | Non-blocking findings: unused imports, unused variables |
| `INFO` | 0 | no | Informational notes, suggestions |
| `HINT` | 0 | no | Low-priority hints, refactoring ideas |

Only `ERROR` diagnostics cause a non-zero exit code. Everything else is
advisory. With `--quiet`, only `ERROR` diagnostics are printed.

The {class}`~rude.core.types.Severity` enum is defined in
{mod}`rude.core.types`:

```python
class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"
```

## Setting severity on your rules

Set the `severity` class variable on any {class}`~rude.core.rule.Rule` or
{class}`~rude.core.rule.LineRule` to change its default severity. When
`severity` is not set (or is `None`), the fallback is `Severity.ERROR`.

```python
from collections.abc import Iterator
from typing import ClassVar

from rude import Diagnostic, FileContext, LineRule, Severity


class TodoWithoutTicket(LineRule):
    """Flag TODO comments that lack a ticket reference."""

    code = "ACME100"
    message = "TODO without ticket reference"
    severity: ClassVar[Severity] = Severity.INFO

    def check_line(
        self,
        line: str,
        lineno: int,
        ctx: FileContext,
        *,
        comment_pos: int = -1,
    ) -> Iterator[Diagnostic]:
        if comment_pos < 0:
            return
        comment = line[comment_pos:]
        if "TODO" in comment and not any(t in comment for t in ("JIRA-", "GH-", "#")):
            yield self.diagnostic_at(lineno, comment_pos)
```

This rule reports at `INFO` severity -- it will never cause a non-zero exit
code, and `--quiet` suppresses it entirely.

You can also override severity per diagnostic by passing it to
`diagnostic()` or `diagnostic_at()`:

```python
def check(self, node: Node) -> Iterator[Diagnostic]:
    yield self.diagnostic(node, severity=Severity.WARNING)
```

The resolution order is: per-diagnostic `severity` argument, then the rule's
`severity` class variable, then the fallback `Severity.ERROR`.

## Built-in rule severities

Most built-in rules use the default `ERROR` severity, which means they block
CI just like Flake8. The exceptions are rules where the finding is advisory
rather than a definite problem:

**Pyflakes -- ERROR (control flow and syntax errors):**
F621, F622, F633, F634, F701, F702, F704, F706, F707, F721, F722, F821,
F822, F823, F831, F901 -- these flag broken code (undefined names, invalid
syntax, misplaced `break`/`continue`/`return`).

**Pyflakes -- WARNING (advisory findings):**
F401 (unused import), F402 (import shadowed by loop variable), F403
(wildcard import), F405 (may be undefined from star import), F601/F602
(duplicate dictionary keys), F631/F632 (suspect comparisons), F811
(redefinition of unused name), F824 (declared but never assigned), F841
(assigned but never used), F842 (annotated but never used), and the
F-string/byte-string literal warnings.

**Pycodestyle -- ERROR (default):**
All E-series rules (E111, E201, E225, E501, etc.) default to `ERROR`,
matching Flake8 behavior where every style violation is fatal. The sole
exception is E275 (missing whitespace after keyword), which emits individual
diagnostics at `WARNING` severity.

## CLI behavior

**Exit codes.** `rude check` returns `1` if any `ERROR`-severity diagnostic
was emitted, `0` otherwise. `WARNING`, `INFO`, and `HINT` diagnostics are
printed but do not affect the exit code.

```bash
# Exits 0 even if unused imports are found (F401 is WARNING)
rude check src/ --select=F401

# Exits 1 if any undefined name is found (F821 is ERROR)
rude check src/ --select=F821
```

**`--quiet` flag.** Suppresses all diagnostics below `ERROR`:

```bash
# Only shows errors -- warnings, info, and hints are hidden
rude check src/ --quiet
```

The summary line always distinguishes errors from non-errors:

```text
Found 3 error(s) and 12 warning(s)
```

## Comparison with other tools

| Tool | Severity model | Exit code behavior |
|---|---|---|
| **Rude** | 4 levels (`ERROR`, `WARNING`, `INFO`, `HINT`) | `exit 1` only for `ERROR` |
| **Ruff** | All findings are errors | Any diagnostic causes `exit 1` |
| **Flake8** | All findings are errors | Any diagnostic causes `exit 1` |
| **Fixit** | All findings are errors | Any diagnostic causes `exit 1` |
| **Pylint** | Bitmask system (fatal, error, warning, refactor, convention) | Exit code is a bitmask of triggered categories |

Ruff, Flake8, and Fixit treat every diagnostic as fatal -- a single unused
import fails CI. Pylint uses a bitmask where the exit code encodes which
categories fired, but the encoding is non-trivial to parse in scripts.

Rude takes a middle path: rules opt into their severity at definition time,
and only `ERROR` diagnostics block the pipeline. This lets teams adopt rules
like F401 (unused import) or custom informational checks without breaking
their build, while keeping genuine errors fatal by default.
