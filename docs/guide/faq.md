# FAQ

## General

### Rude vs Ruff — when should I use which?

Use **Ruff** for standard rules (PEP 8, import sorting, code modernization)
and formatting. Use **Rude** when you need **custom rules** specific to your
project, or **semantic analysis** (scopes, bindings) in your lint rules.

Most teams use both: Ruff for standard checks, Rude for project-specific
conventions.

```bash
ruff check src/ && rude check src/ && ruff format src/
```

See {doc}`comparison` for a detailed comparison.

### Can I use Rude without Ruff?

Yes. Rude works standalone and includes 104 built-in rules (pyflakes,
pycodestyle, McCabe). Additional rules can be added via third-party
plugins or local rules. However, Rude does not provide formatting or
import sorting — Ruff handles those better.

### What Python versions does Rude support?

Rude requires **Python 3.11 or later**. It can lint code targeting any
Python version.

## Configuration

### How do I ignore a rule on one line?

Use a `# noqa` comment with the rule code:

```python
eval(user_input)  # noqa: PAT008
```

### How do I ignore a rule for an entire file?

Add a `# noqa` comment at the top of the file is not supported. Instead,
use per-rule file filtering in your custom rule's `should_check_file()`
method, or pass only the paths you want to check:

```bash
rude check src/ --ignore PAT008
```

### How do I ignore a rule globally?

Add it to the `ignore` list in `pyproject.toml`:

```toml
[tool.rude]
ignore = ["E501", "PAT004"]
```

### How do I exclude files or directories?

Rude automatically skips common directories (`.venv`, `__pycache__`, etc.)
and respects your `.gitignore`. To exclude additional paths, add them to
`.gitignore` or pass only the directories you want:

```bash
rude check src/ tests/  # only lint these directories
```

See {doc}`configuration` for details.

## Custom rules

### How do I write a test for my custom rule?

Use the `Linter` class to check source strings directly:

```python
from rude import Linter

def test_my_rule_flags_issue():
    from my_rules import MyRule

    linter = Linter()
    linter.register(MyRule())
    diagnostics = list(linter.check_source("bad_code_here\n"))
    assert any(d.code == "PROJ001" for d in diagnostics)

def test_my_rule_clean():
    from my_rules import MyRule

    linter = Linter()
    linter.register(MyRule())
    diagnostics = list(linter.check_source("clean_code_here\n"))
    assert not any(d.code == "PROJ001" for d in diagnostics)
```

For autofix tests, use the `assert_fix` helper (see {doc}`/contributing`).

### How do I access scopes and bindings in a custom rule?

Declare a dependency on `ScopeProvider`:

```python
from rude.providers import ScopeProvider

class MySemanticRule(Rule):
    code = "PROJ010"
    message = "..."
    node_types = {NodeType.FUNCTION_DEFINITION}
    metadata_dependencies = {ScopeProvider}

    def check(self, node):
        model = node.get_metadata(ScopeProvider).model
        if model is None:
            return
        scope_id = model.scope_at(node)
        # ... use scope/bindings
```

See {doc}`metadata-providers` for the full walkthrough.

## Troubleshooting

### Rust compilation error during installation

If `pip install rude` fails with a Rust error, you're building from source
and need a Rust toolchain:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
pip install rude
```

Pre-built wheels are available for most platforms — this error typically
means no wheel exists for your OS/architecture combination. If you're on
a common platform and still see this error, please
[open an issue](https://github.com/rude-dev/rude/issues).

### "No rules selected" error

This means your `--select` filter didn't match any registered rules. Check:

- Rule codes are case-sensitive (`PAT`, not `pat`)
- Prefix matching: `F` matches `F401`, `F811`, etc.
- Plugin rules may not be installed
