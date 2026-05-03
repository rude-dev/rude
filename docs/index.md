```{raw} html
<header class="rude-hero">
  <img src="_static/logo-mask.svg" alt="Rude" class="rude-logo"/>

  <p id="tagline">
    <span class="tagline-option">Write custom lint rules in Python. Run them at Rust speed.</span>
    <span class="tagline-option">The custom rules linter that Ruff can't be and Flake8 refuses to become.</span>
    <span class="tagline-option">Your rules. Python API. Rust engine.</span>
    <span class="tagline-option">17x faster than Flake8. 2x faster on 1 core than Flake8 on 16.</span>
    <span class="tagline-option">Ruff for standards. Rude for <em>your</em> standards.</span>
    <span class="tagline-option">Custom lint rules shouldn't cost you 1 GB of RAM.</span>
    <span class="tagline-option">Flake8 refused <code>pyproject.toml</code>. We refused Flake8.</span>
    <span class="tagline-option">Flake8 speed at 16 cores. Rude speed at 1.</span>
    <span class="tagline-option">Scopes, bindings, qualified names — in your Python rules, at zero cost.</span>
  </p>

  <p class="badges">
    <a href="https://github.com/rude-dev/rude/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/pypi/l/rude?label=License"></a>
    <a href="https://pypi.org/project/rude/"><img alt="Python versions" src="https://img.shields.io/pypi/pyversions/rude?label=Python"></a>
    <a href="https://pypi.org/project/rude/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/rude?label=Latest"></a>
  </p>

  <hr/>
<!--
  <figure>
    <img src="_static/benchmark-tier1.svg" alt="Tier 1 — Django, single process" width="496"/>
    <figcaption>Linting Django (901 files) — 10 equivalent rules, single process.
    <a href="guide/comparison.html">Full benchmark →</a></figcaption>
  </figure>
  -->
</header>
```

# Rude

Rude is a fast, extensible Python linter built for teams that need **their own
rules** — not just PEP 8. It pairs a [tree-sitter](https://tree-sitter.github.io/)
parser with a Rust-powered semantic engine to give your Python rules access to
scopes, bindings, and qualified names — without the overhead.

## Getting started

```bash
pip install rude
rude check src/
```

See the [installation guide](guide/installation) and [quickstart](guide/quickstart)
for more options.

## Write your first rule

```python
from collections.abc import Iterator

from rude import Diagnostic, Node, NodeType, Rule


class NoAssertInProd(Rule):
    """ACME001 - `assert` should not appear in production code.

    Skips the check in test files (whose path contains a `tests/` or
    `test/` segment, or whose name starts with `test_` / ends with
    `_test.py`) so the rule does not flag test-suite assertions.
    """

    code = "ACME001"
    message = "`assert` should not appear outside test files"
    node_types = {NodeType.ASSERT_STATEMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if node.ctx.is_test_file():
            return
        yield self.diagnostic(node)
```

See the [custom rules guide](guide/custom-rules) for autofixes, plugins,
and advanced patterns.

## Key features

- **Fast** — tree-sitter parsing + Rust semantic engine (~17x faster than Flake8; `--jobs=N` for multiprocess Python rule parallelism)
- **Autofix** — Rules can provide automatic fixes with import management
- **Advanced analysis** — Scope tracking, qualified name resolution via Rust/PyO3
- **Extensible** — Simple Python API: `Rule` and `LineRule` base classes
- **Plugin system** — Entry points + local rules + `pyproject.toml` config
- **Error recovery** — Lints partially even with syntax errors

## The sweet spot

| | Standard rules | Custom rules | Speed | Memory |
|---|---|---|---|---|
| **Ruff** | 800+ | none | fastest | low |
| **Rude** | 147 (104 + plugins) | unlimited | fast | low |
| **Flake8** | 100+ (plugins) | via packages | slow | medium |
| **Fixit** | ~30 | via LibCST | slow | high |

## Why not just use...

**Ruff?** Ruff is incredible for standard rules — but it doesn't support custom
rules in Python. Rude is designed as a **companion** to Ruff, not a replacement.

**Flake8?** Flake8 is 17x slower, still can't read `pyproject.toml` without a
[third-party plugin](https://pypi.org/project/Flake8-pyproject/), and requires
publishing a package just to add a custom rule.

**Fixit?** Fixit uses 17x more memory than Rude on the same codebase (1,059 MB vs
61 MB on Django), has no parallel execution, and users report
[hour-long CI runs](https://github.com/Instagram/Fixit/issues/457).

```{toctree}
:maxdepth: 2

Why Rude? <guide/comparison>
```

```{toctree}
:maxdepth: 2
:caption: Getting Started

guide/installation
guide/quickstart
guide/cli
guide/configuration
```

```{toctree}
:maxdepth: 2
:caption: Writing Rules

guide/custom-rules
guide/plugin-development
guide/metadata-providers
```

```{toctree}
:maxdepth: 2
:caption: Guides

guide/migrating-from-flake8
guide/severity
guide/ci-integration
guide/architecture
guide/faq
```

```{toctree}
:maxdepth: 2
:caption: Built-in Rules

rules/index
```

```{toctree}
:maxdepth: 2
:caption: API Reference

api/core
api/rules
api/providers
api/semantic
```

```{toctree}
:maxdepth: 1
:caption: Project

changelog
contributing
coding-assistants
```
