# Plugin development

Rude supports two ways to extend its rule set: **entry-point plugins**
(distributed as installable packages) and **local rules** (plain Python files
referenced in config). This guide covers both approaches.

## Installing community plugins

Community plugins are installed directly by package name:

```bash
pip install rude-mycompany-rules
```

They register via the `rude.plugins` entry point. Rude discovers them
automatically at startup -- no configuration needed.

## Entry-point plugins

Entry-point plugins are the standard way to distribute reusable rules. They
are regular Python packages that register themselves via the `rude.plugins`
entry point.

### Project structure

A typical plugin layout:

```text
rude-django/
├── pyproject.toml
├── src/
│   └── rude_django/
│       ├── __init__.py
│       └── rules.py
└── tests/
    └── test_rules.py
```

### Define your rules

```python
# src/rude_django/rules.py
from rude import Diagnostic, Node, NodeType, Rule
from typing import ClassVar, Iterator


class NoQuerysetRawSQL(Rule):
    """Flag usage of RawSQL in querysets."""

    code: ClassVar[str] = "DJ001"
    message: ClassVar[str] = "Avoid RawSQL(); use ORM expressions instead"
    node_types = {NodeType.CALL}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if node.function_name == "RawSQL":
            yield self.diagnostic(node)


class NoModelStar(Rule):
    """Flag 'from app.models import *' in views."""

    code: ClassVar[str] = "DJ002"
    message: ClassVar[str] = "Do not use 'from ... import *' for models"
    node_types = {NodeType.IMPORT_FROM_STATEMENT}

    def should_check_file(self, ctx):
        return ctx.is_in_path("/views/", "/views.py")

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if any(c.type == "wildcard_import" for c in node.children):
            text = node.text
            if "models" in text:
                yield self.diagnostic(node)
```

### Export a `RULES` list

The plugin's top-level module must expose a `RULES` list containing the rule
classes:

```python
# src/rude_django/__init__.py
from rude_django.rules import NoQuerysetRawSQL, NoModelStar

RULES = [NoQuerysetRawSQL, NoModelStar]
```

### Register the entry point

In `pyproject.toml`, register the plugin under the `rude.plugins` entry-point
group:

```toml
# pyproject.toml for rude-django
[project]
name = "rude-django"
version = "0.1.0"
description = "Django rules for Rude linter"
requires-python = ">=3.11"
dependencies = ["rude>=0.1a2"]

[project.entry-points."rude.plugins"]
rude_django = "rude_django"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

The entry-point name (left side, `rude_django`) is arbitrary. The value (right
side, `"rude_django"`) is the Python module that Rude will import. That module
must have a `RULES` attribute.

### Install and use

```bash
# Install the plugin (from local source or PyPI)
pip install rude-django

# Rules are auto-discovered via entry points
rude check src/

# Or explicitly enable the plugin's prefix
rude check --select DJ src/
```

Auto-discovery means the plugin's rules are loaded automatically whenever
Rude runs, without any config changes. Users can still filter them with
`--select` and `--ignore` as with any other rules.

### Testing your plugin

Test plugin rules by instantiating the `Linter` directly:

```python
# tests/test_rules.py
from rude import Linter
from rude_django.rules import NoQuerysetRawSQL


def test_raw_sql_flagged():
    linter = Linter()
    linter.register(NoQuerysetRawSQL())

    diagnostics = list(linter.check_source("""
from django.db.models.expressions import RawSQL
qs = Model.objects.annotate(val=RawSQL("select 1"))
"""))
    assert any(d.code == "DJ001" for d in diagnostics)


def test_raw_sql_clean():
    linter = Linter()
    linter.register(NoQuerysetRawSQL())

    diagnostics = list(linter.check_source("""
from django.db.models import F
qs = Model.objects.annotate(val=F("field"))
"""))
    assert not any(d.code == "DJ001" for d in diagnostics)
```

### Testing autofixes

If your plugin rules provide fixes, test them with `Linter.fix_source()`:

```python
def test_autofix_applied():
    linter = Linter()
    linter.register(MyFixableRule())

    diagnostics, result = linter.fix_source("x == None\n")
    assert result is not None
    assert "x is None" in result.source
    assert len(result.applied) == 1
```

For simpler assertions, use the `assert_fix` and `assert_no_fix` helpers
from the public `rude.testing` module:

```python
from rude.testing import assert_fix, assert_no_fix


def test_my_rule_fix():
    from rude_myplugin.rules import MyFixableRule

    assert_fix(MyFixableRule, "x == None\n", "x is None\n")
```

`rude.testing` is the stable, published home of these helpers; they are
safe to import from plugin test suites.

## Local rules

For project-specific rules that do not need to be packaged and distributed,
use **local rules**. These are plain Python files loaded directly by Rude.

```{important}
Local rule files are **executed as Python modules** (via `importlib`).
Only load files you trust -- a local rule has the same capabilities as
any Python script run in your environment. In CI, audit `local-rules`
paths to ensure they point to files under version control.
```

### Setup

Create a rule file anywhere in your project:

```python
# tools/lint_rules.py
from rude import Diagnostic, Node, NodeType, Rule
from typing import ClassVar, Iterator


class NoDirectDBAccess(Rule):
    """All database access must go through the repository layer."""

    code: ClassVar[str] = "PROJ001"
    message: ClassVar[str] = "Direct database access; use the repository layer"
    node_types = {NodeType.CALL}

    def should_check_file(self, ctx):
        return ctx.is_in_path("src/api/", "src/views/")

    def check(self, node: Node) -> Iterator[Diagnostic]:
        name = node.full_call_name or node.function_name
        if name and name.startswith(("db.session", "Session.query")):
            yield self.diagnostic(node)


RULES = [NoDirectDBAccess]
```

### Configure

Reference the file in `pyproject.toml`:

```toml
[tool.rude]
local-rules = ["tools/lint_rules.py"]
```

Paths are resolved relative to the `pyproject.toml` location. You can also
point to a directory:

```toml
[tool.rude]
local-rules = ["tools/rules/"]
```

When a directory is given, Rude loads all `.py` files in it (excluding files
starting with `_`).

### Discovery behavior

If the file exports a `RULES` list, only those classes are loaded. Otherwise,
Rude auto-discovers all `Rule` subclasses in the module that have a `code`
attribute defined.

## Naming conventions

Choose a code prefix that is unlikely to collide with other plugins:

| Prefix   | Suggested use               |
|----------|-----------------------------|
| `DJ`     | Django                       |
| `FL`     | Flask                        |
| `PROJ`   | Project-specific local rules |
| `ACME`   | Organization-specific rules  |
| `SEC`    | Security rules               |

Built-in prefixes (`PAT`, `META`, `EX`, `F`, `E`, `W`, `C`) are reserved.

## Plugin checklist

Before publishing a plugin:

- [ ] All rule classes have unique `code` attributes
- [ ] A `RULES` list is exported from the package's top-level `__init__.py`
- [ ] The `rude.plugins` entry point is declared in `pyproject.toml`
- [ ] Rules are tested with `Linter.check_source()`
- [ ] `rude` is listed as a dependency (`requires = ["rude>=0.1a2"]`)
