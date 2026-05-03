# Roadmap

## v0.1a2 (current)

First public release. The plugin architecture is in place, the API uses
frozen pyclasses with named fields, and the core ships with the
flake8-equivalent rule set (pycodestyle + pyflakes + mccabe).

**Done:**
- Frozen pyclasses for SemanticModel API (no more tuple indexing)
- GIL released during single-file analysis
- `scope_for_position` early-exit optimization
- Thread-local parser reuse in single-file path
- abi3 wheels (CPython 3.11+) for Linux (manylinux + musllinux), macOS, and
  Windows
- Code coverage with codecov

**Before tagging:**
- OIDC trusted publishing setup on PyPI
- ReadTheDocs project linked to `docs.rude.dev`

## v0.1.1

Quick wins post-release.

- **Python SAST scanning** -- add bandit, semgrep, or CodeQL to CI
- **`cargo-deny`** -- license and source auditing for Rust dependencies
- **Post-release verification** -- `pip install rude && rude --version` smoke
  test after publish
- **`--diff` mode** -- preview fixes as unified diff without applying
- **Pre-commit hook** -- `.pre-commit-hooks.yaml` for out-of-the-box
  integration
- **Official plugin packages** -- bugbear, pyupgrade, and comprehensions rules
  shipped as standalone packages under the `rude-dev` org

## v0.2

Architecture improvements and new features.

- **`analyzer.rs` decomposition** -- extract the 343-line `analyze_node` match
  block into named handlers
- **NodeType enum redesign** -- evaluate moving from string-based to a more
  type-safe approach
- **String interning** -- intern repeated identifiers (self, None, True) for
  5-10% analysis speedup
- **Rust unit tests** -- test core analyzer natively via
  `pyo3::prepare_freethreaded_python()`
- **Rust code coverage** -- measure Rust extension coverage via llvm-cov or
  cargo-tarpaulin
- **Lint-as-config (rule types)** -- define custom rules purely in
  `pyproject.toml` with built-in rule types (`require-base-class`,
  `forbidden-call`, `require-decorator`, `require-fields`). User picks code,
  message, severity, and paths -- no Python needed. Replaces the current EX
  template rules with a first-class framework feature.
- **`rude init`** -- scaffold a rule file and TOML config in one command
- **`rude explain <code>`** -- display rule documentation, options, and example
- **SARIF output** -- `--format sarif` for GitHub Code Scanning

## Later

Ideas under consideration. Not committed to a timeline.

- **Watch mode** -- `rude --watch src/` for live feedback during rule
  development
- **LSP / language server** -- real-time diagnostics in IDEs
- **Per-path rule config** -- `[tool.rude.rules.ACME001] paths = ["src/"]` for
  any rule
- **Inline disable comments** -- `# rude: disable=ACME001` as alternative to
  `# noqa`
- **Post-fix hooks** -- run formatter automatically after applying fixes
- **Flake8 compatibility suite** -- comparing Rude output against flake8 on
  edge-case fixtures, ideally as a dedicated out-of-repo harness.
