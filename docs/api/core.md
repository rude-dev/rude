# Core API

The core API provides the building blocks for writing rules and using the linter.

## Rules

The {class}`~rude.core.rule.Rule` and {class}`~rude.core.rule.LineRule` base
classes are the foundation for all lint rules. See the {doc}`/guide/custom-rules`
guide for usage examples.

```{eval-rst}
.. automodule:: rude.core.rule
   :members:
   :show-inheritance:
```

## Types

Core data types used throughout the API, including
{class}`~rude.core.types.Diagnostic`, {class}`~rude.core.types.FileContext`,
and {class}`~rude.core.types.Fix`.

```{eval-rst}
.. automodule:: rude.core.types
   :members:
   :show-inheritance:
```

## Node

The {class}`~rude.core.node.Node` wrapper around tree-sitter nodes, providing
a Pythonic API for AST navigation and inspection. See the
{doc}`/guide/custom-rules` guide for a quick reference table of all
Node properties and methods.

```{eval-rst}
.. automodule:: rude.core.node
   :members:
   :show-inheritance:
```

## Node Types

Named constants for tree-sitter node types, used in rule `node_types` sets
for IDE autocomplete and typo prevention.

```{eval-rst}
.. automodule:: rude.core.node_types
   :members:
   :show-inheritance:
```

## Linter

The {class}`~rude.core.linter.Linter` class is the main entry point for
running rules programmatically. See the {doc}`/guide/quickstart` for CLI
usage and {doc}`/guide/plugin-development` for testing rules.

```{eval-rst}
.. automodule:: rude.core.linter
   :members:
   :show-inheritance:
```

## Configuration

Handles `pyproject.toml` parsing and rule selection. See the
{doc}`/guide/configuration` guide for user-facing documentation.

```{eval-rst}
.. automodule:: rude.core.config
   :members:
```

## Parser

Tree-sitter parser interface for parsing Python source into syntax trees.

```{eval-rst}
.. automodule:: rude.core.parser
   :members:
```

## Rule Discovery

Discovers and loads rules from entry points, local files, and plugins.
See {doc}`/guide/plugin-development` for the plugin loading mechanism.

```{eval-rst}
.. automodule:: rude.core.rule_discovery
   :members:
```

## File Finder

Discovers Python files with `.gitignore` support and automatic directory
skipping. See {doc}`/guide/configuration` for the file filtering
documentation.

```{eval-rst}
.. automodule:: rude.core.file_finder
   :members:
```
