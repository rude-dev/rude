# Installation

## From PyPI

The easiest way to install Rude is from PyPI. Pre-built wheels are available for
Linux, macOS, and Windows:

```bash
pip install rude                    # core: pycodestyle (E/W) + pyflakes (F) + mccabe (C)
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add rude
```

### Plugins

Additional rule sets can be added via third-party plugin packages or
local rules. See {doc}`plugin-development` for how to write or install
plugins.

## From source

Building from source requires a Rust toolchain because Rude includes a
compiled Rust extension (via [PyO3](https://pyo3.rs/)) for high-performance
semantic analysis.

### Prerequisites

- **Python 3.11 or later**
- **Rust toolchain** -- install via [rustup](https://rustup.rs/):

  ```bash
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
  ```

- **uv** (recommended) -- install via the [official installer](https://docs.astral.sh/uv/getting-started/installation/):

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Build steps

```bash
git clone https://github.com/rude-dev/rude.git
cd rude

# Install Python dependencies
uv sync

# Build the Rust extension in release mode
uv run maturin develop --release
```

The `maturin develop` command compiles the Rust code (including a vendored
tree-sitter parser — no separate tree-sitter Python package needed) and
installs it as a native Python extension module (`rude._rust`) into the
active virtual environment.

:::{tip}
During development, you can omit `--release` for faster compile times at
the cost of slower runtime performance:

```bash
uv run maturin develop
```
:::

## Verify the installation

```bash
rude --version
```

This should print the installed version, for example:

```text
rude 0.1a2
```

You can also verify that rules load correctly:

```bash
rude list
```

## Editor integration

Rude outputs diagnostics in standard formats that work with most editors and
CI tools:

- **Text** (default) -- human-readable output with colors
- **Compact** -- single-line format compatible with `errorformat` in Vim and
  similar tools
- **JSON** -- machine-readable, one JSON object per line

See the {doc}`quickstart` guide for details on output formats.
