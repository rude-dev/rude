"""
Built-in rules for Rude.

Categories:
- F: Pyflakes-style rules (unused variables, imports, syntax errors)
- E: Pycodestyle errors (style errors)
- W: Pycodestyle warnings (style warnings)
- C: McCabe complexity rules

Additional rules can be added via third-party plugins (registered under the
`rude.plugins` entry point) or via local rules (see `examples/rules/`).
"""

from rude.core.rule import RuleBase
from rude.rules.mccabe import MCCABE_RULES
from rude.rules.pycodestyle import PYCODESTYLE_RULES
from rude.rules.pyflakes import PYFLAKES_RULES

# Built-in rules (flake8 equivalent)
ALL_RULES: list[type[RuleBase]] = [
    *PYFLAKES_RULES,
    *PYCODESTYLE_RULES,
    *MCCABE_RULES,
]
