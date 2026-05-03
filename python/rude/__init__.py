"""
Rude - A fast, extensible Python linter for custom rules.

Complements Ruff by providing a Python-native way to write custom rules.

Example::

    from rude import Linter, Rule, Node, NodeType, Fix

    class NoDebugPrint(Rule):
        code = "DBG001"
        message = "Debug print() found"
        node_types = {NodeType.CALL}

        def check(self, node: Node):
            if node.function_name == "print":
                yield self.diagnostic(node, fix=Fix.delete(node))

    linter = Linter()
    linter.register(NoDebugPrint())

    for diag in linter.check_file("src/main.py"):
        print(diag)

    # With autofix
    diagnostics, result = linter.fix_file("src/main.py")
    if result:
        Path("src/main.py").write_text(result.source)
"""

__version__ = "0.1a2"

from rude import rules
from rude.core import (
    CheckOptions,
    Config,
    # Types
    Diagnostic,
    Edit,
    FileContext,
    Fix,
    FixResult,
    LineRule,
    # Main classes
    Linter,
    Location,
    Node,
    NodeLike,
    NodeType,
    Rule,
    RuleBase,
    Severity,
    # Discovery
    discover_rules,
    find_python_files,
    load_config,
    # Parser
    parse,
    parse_file,
    parse_string,
    resolve_paths,
)
from rude.providers import (
    Binding,
    ParentProvider,
    QualifiedNameProvider,
    Scope,
    ScopeProvider,
    ScopeType,
)

__all__ = [
    "Binding",
    "CheckOptions",
    "Config",
    "Diagnostic",
    "Edit",
    "FileContext",
    "Fix",
    "FixResult",
    "LineRule",
    # Core
    "Linter",
    "Location",
    "Node",
    "NodeLike",
    "NodeType",
    # Providers
    "ParentProvider",
    "QualifiedNameProvider",
    "Rule",
    "RuleBase",
    "Scope",
    "ScopeProvider",
    "ScopeType",
    "Severity",
    "__version__",
    "discover_rules",
    "find_python_files",
    "load_config",
    "parse",
    "parse_file",
    "parse_string",
    "resolve_paths",
    # Submodules
    "rules",
]
