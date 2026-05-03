# Contributing

Contributions are welcome! This guide covers development setup and workflow.

## Development setup

Rude is a hybrid Python/Rust project. You need:

- Python 3.11+
- Rust toolchain ([rustup](https://rustup.rs/))
- [uv](https://docs.astral.sh/uv/) package manager

```bash
git clone https://github.com/rude-dev/rude.git
cd rude
uv sync
uv run maturin develop --release
```

## Running tests

```bash
make test
```

## Code generation

The `node_types.py` module is auto-generated from tree-sitter-python's grammar.
After updating the tree-sitter grammar or Rust extension, regenerate it:

```bash
make generate
```

This runs `scripts/generate_node_types.py`, which produces
`python/rude/core/node_types.py` with static `Final[NodeType]` constants.

## Code style

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check style
make check

# Auto-format and fix
make fmt
```

## Project structure

```text
├── src/                  # Rust source (PyO3 extension)
│   ├── lib.rs
│   ├── analyzer.rs
│   ├── model.rs
│   ├── scope.rs
│   ├── binding.rs
│   └── import_info.rs
├── python/rude/          # Python package
│   ├── core/             # Linter engine, parser, config
│   ├── rules/            # Built-in rule implementations
│   ├── providers/        # Metadata providers
│   ├── cli.py            # CLI entry point
│   └── _rust.pyi         # Type stubs for Rust extension
├── tests/                # Test suite
├── docs/                 # Sphinx documentation
└── benches/              # Performance benchmarks (criterion + pytest-benchmark)
```

## Writing rules

See the {doc}`guide/custom-rules` guide for how to write new rules.

## Testing rule autofixes

Rules that provide autofixes should be tested with the `assert_fix` and
`assert_no_fix` helpers from the public `rude.testing` module:

```python
from rude.testing import assert_fix, assert_no_fix


def test_e711_comparison_to_none():
    from rude.rules.pycodestyle.comparison import ComparisonToNone

    assert_fix(ComparisonToNone, "x == None\n", "x is None\n")


def test_e711_no_fix_for_is():
    from rude.rules.pycodestyle.comparison import ComparisonToNone

    assert_no_fix(ComparisonToNone, "x is None\n")
```

`assert_fix(RuleClass, before, after)` instantiates the rule, lints the
`before` source with fixes enabled, and checks that the fixed output matches
`after`. `assert_no_fix(RuleClass, source)` verifies the rule produces no
fixable diagnostics for the given source.

## AI coding assistants

AI-assisted contributions are welcome. See {doc}`coding-assistants` for
attribution, human responsibility, and the `Assisted-by` commit trailer
format.

## Pull requests

1. Fork the repository
2. Create a feature branch
3. Write tests for your changes
4. Run `make check` and `make test`
5. Submit a pull request
