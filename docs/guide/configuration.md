# Configuration

Rude is configured via `pyproject.toml` under the `[tool.rude]` section.
Settings from the config file can be overridden by CLI flags.

## Config file discovery

Rude searches upward from the current working directory for a `pyproject.toml`
that contains a `[tool.rude]` section. You can override this with `--config`:

```bash
rude check --config path/to/pyproject.toml src/
```

## Rule selection

### `select`

Enable specific rules or rule prefixes. When set, **only** matching rules are
active:

```toml
[tool.rude]
select = ["PAT", "META", "F"]
```

This enables all rules whose code starts with `PAT`, `META`, or `F`. You can
also specify individual codes:

```toml
[tool.rude]
select = ["PAT001", "PAT008", "F841", "META"]
```

### `ignore`

Exclude rules from the active set. Applied after `select`:

```toml
[tool.rude]
select = ["PAT"]
ignore = ["PAT004"]
```

This enables all pattern rules except `PAT004` (long function).

Both `select` and `ignore` support individual codes (`F841`) and prefixes (`F`).

## Plugins

### Entry-point plugins

Third-party packages can register rules via the `rude.plugins` entry point.
List them in `plugins` to load them explicitly by module name:

```toml
[tool.rude]
plugins = ["rude-django", "rude-flask"]
```

Rude also auto-discovers any installed package that declares the
`rude.plugins` entry point, even without listing it here. The `plugins` option
is for loading modules by name that don't use the entry-point mechanism.

### Local rules

Load rules from local Python files without creating a package:

:::{warning}
`local-rules` and installed plugins execute arbitrary Python at startup.
Only list paths you control, and only install plugins you trust -- see
[SECURITY.md](https://github.com/rude-dev/rude/blob/main/SECURITY.md#trust-model)
for the full trust model.
:::

```toml
[tool.rude]
local-rules = ["tools/rules.py", "tools/extra_rules/"]
```

Paths are resolved relative to the `pyproject.toml` location. If a directory
is given, all `.py` files in it (excluding those starting with `_`) are loaded.

See the {doc}`plugin-development` guide for details on writing plugins and
local rules.

## Per-rule options

Many rules accept configuration via `[tool.rude.rules.<CODE>]` sub-tables:

```toml
[tool.rude.rules.PAT001]
max_params = 7

[tool.rude.rules.PAT004]
max_lines = 100

[tool.rude.rules.META001]
ticket_pattern = "(PROJ-\\d+|#\\d+)"
```

Each rule documents its accepted options. Check the
{doc}`/rules/index` page for built-in rule options.

## Inline suppression

Suppress individual diagnostics with `# noqa` comments:

```python
eval(user_input)  # noqa: PAT008
```

Suppress multiple codes on one line:

```python
eval(user_input)  # noqa: PAT008,F841
```

A blanket `# noqa` (without codes) suppresses all diagnostics on that line,
but is flagged by the `META002` rule as bad practice:

```python
eval(user_input)  # noqa
```

:::{tip}
Always specify the exact codes you intend to suppress. Blanket `# noqa`
comments hide real issues and make code harder to maintain.
:::

## File filtering

Rude automatically skips common non-source directories when scanning for
Python files:

- Version control: `.git`, `.hg`, `.svn`
- Virtual environments: `.venv`, `venv`, `.env`, `env`
- Build artifacts: `dist`, `build`, `*.egg-info`, `.eggs`
- Cache directories: `__pycache__`, `.mypy_cache`, `.pytest_cache`,
  `.ruff_cache`, `.hypothesis`, `.coverage`, `htmlcov`
- Others: `node_modules`, `.tox`, `.nox`, `.ipynb_checkpoints`

Additionally, Rude respects your project's `.gitignore` file. Any path
matched by `.gitignore` is excluded from linting.

:::{tip}
To exclude specific paths from linting, add them to your `.gitignore` or
pass only the directories you want to check:

```bash
# Lint only src/ and tests/, ignoring everything else
rude check src/ tests/
```
:::

For per-rule file filtering, use `should_check_file()` in custom rules
(see {doc}`custom-rules`) or the `paths` option on template rules:

```toml
[tool.rude.rules.EX003]
forbidden = ["print"]
paths = ["src/"]
exclude_paths = ["src/scripts/"]
```

## Complete example

```toml
[tool.rude]
# Enable pattern, hygiene, pyflakes, and pycodestyle rules
select = ["PAT", "META", "F", "E", "W"]

# Ignore line-length (handled by formatter) and long-function checks
ignore = ["E501", "PAT004"]

# Load a third-party plugin
plugins = ["rude-django"]

# Load project-specific local rules
local-rules = ["tools/lint_rules.py"]

# --- Per-rule configuration ---

[tool.rude.rules.PAT001]
max_params = 7

[tool.rude.rules.PAT002]
max_branches = 15

[tool.rude.rules.PAT003]
max_depth = 5

[tool.rude.rules.PAT005]
max_methods = 25

[tool.rude.rules.META001]
ticket_pattern = "(PROJ-\\d+|#\\d+)"

# --- Template rules (require configuration to activate) ---

[tool.rude.rules.EX001]
pattern = "*Service"
required_base = "BaseService"
paths = ["src/services/"]

[tool.rude.rules.EX002]
required_decorator = "audit_log"
paths = ["src/api/"]
exclude_pattern = "_*"

[tool.rude.rules.EX003]
forbidden = ["print", "pdb.set_trace", "breakpoint"]
paths = ["src/"]
exclude_paths = ["src/scripts/", "tests/"]

[tool.rude.rules.EX004]
pattern = "*Model"
required_fields = ["created_at", "updated_at"]
paths = ["src/models/"]
```

## Integration with Ruff

Rude is designed to complement [Ruff](https://docs.astral.sh/ruff/), not
replace it. A typical workflow chains both tools:

```bash
# Lint with Ruff (standard rules) + Rude (custom rules), then format
ruff check src/ && rude check src/ && ruff format src/
```

Or in a Makefile:

```makefile
.PHONY: lint

lint:
	ruff check src/ tests/
	rude check src/ tests/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/
	rude check --fix src/ tests/
```

Since Rude focuses on custom and organization-specific rules, there is minimal
overlap with Ruff's built-in rule set. Use Ruff for standard PEP 8 style,
import sorting, and code upgrades. Use Rude for project-specific conventions,
complexity checks, and rules that need semantic analysis.
