"""
Semantic model for Python scope and binding analysis.

Uses the Rust/PyO3 implementation for high-performance analysis.
The entire AST traversal and scope building is done in Rust with
a single call to analyze_source().
"""

from __future__ import annotations

from enum import IntEnum
from typing import NewType

# ─────────────────────────────────────────────────────────────────────────────
# Types
# ─────────────────────────────────────────────────────────────────────────────

ScopeId = NewType("ScopeId", int)

# Sentinel for "no scope"
NO_SCOPE: ScopeId = ScopeId(-1)


class ScopeType(IntEnum):
    """Scope type enumeration - compatible with Rust constants."""

    MODULE = 1
    CLASS = 2
    FUNCTION = 3
    COMPREHENSION = 4


# ─────────────────────────────────────────────────────────────────────────────
# Rust Extension (Required)
# ─────────────────────────────────────────────────────────────────────────────

# Ancestor context flags and core types from Rust extension
from rude._rust import (
    CTX_IN_CLASS as CTX_IN_CLASS,
    CTX_IN_COMPREHENSION as CTX_IN_COMPREHENSION,
    CTX_IN_EXCEPT as CTX_IN_EXCEPT,
    CTX_IN_FINALLY as CTX_IN_FINALLY,
    CTX_IN_FUNCTION as CTX_IN_FUNCTION,
    CTX_IN_LAMBDA as CTX_IN_LAMBDA,
    CTX_IN_LOOP as CTX_IN_LOOP,
    CTX_IN_TRY as CTX_IN_TRY,
    CTX_IN_WITH as CTX_IN_WITH,
    SCOPE_CLASS as SCOPE_CLASS,
    SCOPE_COMPREHENSION as SCOPE_COMPREHENSION,
    SCOPE_FUNCTION as SCOPE_FUNCTION,
    SCOPE_MODULE as SCOPE_MODULE,
    Binding as Binding,
    ImportInfo as ImportInfo,
    Scope as Scope,
    SemanticModel as SemanticModel,
    analyze_source as analyze_source,
    group_nodes as group_nodes,
)

__all__ = [
    "CTX_IN_CLASS",
    "CTX_IN_COMPREHENSION",
    "CTX_IN_EXCEPT",
    "CTX_IN_FINALLY",
    "CTX_IN_FUNCTION",
    "CTX_IN_LAMBDA",
    "CTX_IN_LOOP",
    "CTX_IN_TRY",
    "CTX_IN_WITH",
    "NO_SCOPE",
    "SCOPE_CLASS",
    "SCOPE_COMPREHENSION",
    "SCOPE_FUNCTION",
    "SCOPE_MODULE",
    "Binding",
    "ImportInfo",
    "Scope",
    "ScopeId",
    "ScopeType",
    "SemanticModel",
    "analyze_source",
    "group_nodes",
]
