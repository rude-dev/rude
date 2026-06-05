# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## 0.1a4 -- Bug fixes and Node API ergonomics

### Added
- `Node` ergonomics helpers on the abstract `_NodeTypeMixin` contract.
- `Node.docstring` property and import alias helpers (`iter_import_aliases`,
  `ImportAlias`).
- `rude.testing.assert_fix` and `assert_no_fix` accept `options` and `filename`
  keyword arguments.

### Fixed
- F507: gate on tuple-literal right-hand side to avoid false positives on
  dynamic format arguments.
- E703 autofix uses byte length on UTF-8 lines so multi-byte characters no
  longer break the replacement range.
- `Location.column` reports character offsets instead of byte offsets, matching
  the documented contract.
- E231 fires on dict and annotation colons (previously skipped).
- File finder loads nested `.gitignore` files, not just the repository root.
- Percent format rules (E.g. F501) strip `r`/`b`/`f` string prefixes before
  parsing.
- Analyzer strips the string prefix when parsing `__all__` literals so prefixed
  string entries are tracked.
- Batch mode surfaces unreadable and unparsable files as diagnostics instead of
  silently skipping them.
- Worker enforces `timeout_per_file` per file (previously applied to the whole
  batch).

## 0.1a3 -- README image rendering on PyPI

### Fixed
- README images now render on PyPI by using absolute URLs instead of repo-relative paths.

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
