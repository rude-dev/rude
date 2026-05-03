# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## 0.1a2 -- Initial public release

First public release of Rude.

### Highlights
- 104 built-in rules: pyflakes (F), pycodestyle (E/W), and mccabe (C901)
- Rust-powered semantic analysis via PyO3 (scopes, bindings, qualified names)
- Autofix engine with atomic conflict detection and import management
- Plugin system via the `rude.plugins` entry-point group
- Local rules via `[tool.rude]` configuration
- Frozen pyclass API surface (`Binding`, `Scope`, `ImportInfo`, `NodeEntry`,
  `LineInfo`) with named fields
- Multi-process mode (`--jobs=N`) and a streaming single-process path that
  honors `--max-errors` / `--fail-fast`
- Public test helpers in `rude.testing` (`assert_fix`, `assert_no_fix`)
- Output formats: text, compact, and JSON
- Vendored tree-sitter (no separate `tree-sitter` Python dependency)
- abi3 wheels for CPython 3.11+ on Linux (manylinux + musllinux), macOS, and
  Windows
