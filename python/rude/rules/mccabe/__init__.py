"""
McCabe complexity rules for Rude.

C9xx: Complexity
"""

from rude.rules.mccabe.complexity import COMPLEXITY_RULES, FunctionTooComplex

MCCABE_RULES = COMPLEXITY_RULES

__all__ = [
    "COMPLEXITY_RULES",
    "MCCABE_RULES",
    "FunctionTooComplex",
]
