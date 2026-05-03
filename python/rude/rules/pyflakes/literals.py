"""
String literal rules.

F541: FStringMissingPlaceholders - f-string without placeholders
F542: TStringMissingPlaceholders - t-string without placeholders (Python 3.14+)
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Fix, Severity

if TYPE_CHECKING:
    from rude.core.node import Node


class _PrefixStringMissingPlaceholders(Rule):
    """Base for f-string/t-string missing placeholder rules."""

    _PREFIX_CHAR: ClassVar[str]
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.STRING}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        text = node.text

        if not self._has_prefix(text):
            return

        # Check if it has any interpolation children (direct children only)
        has_placeholder = any(c.type == "interpolation" for c in node.children)

        if not has_placeholder:
            new_text = self._remove_prefix(text)
            yield self.diagnostic(
                node,
                fix=Fix.replace(
                    node, new_text, description=f"Remove {self._PREFIX_CHAR}-string prefix"
                ),
            )

    def _has_prefix(self, text: str) -> bool:
        """Check if string literal has the expected prefix."""
        lower = text.lstrip()[:3].lower()
        p = self._PREFIX_CHAR
        return lower.startswith(p) or lower.startswith(f"r{p}") or lower.startswith(f"{p}r")

    def _remove_prefix(self, text: str) -> str:
        """Remove the prefix character from string literal."""
        stripped = text.lstrip()
        lower = stripped[:3].lower()
        p = self._PREFIX_CHAR

        if lower.startswith(f"r{p}"):
            # rX"..." -> r"..."
            return stripped[0] + stripped[2:]
        elif lower.startswith(f"{p}r"):
            # Xr"..." -> r"..."
            return stripped[1:]
        elif lower.startswith(p):
            # X"..." -> "..."
            return stripped[1:]
        return text


class FStringMissingPlaceholders(_PrefixStringMissingPlaceholders):
    """
    F541: f-string without any placeholders.

    An f-string without placeholders is probably a mistake - the `f`
    prefix should be removed.

    Example::

        x = f"hello"       # F541 - no placeholders
        x = f"hello {x}"   # OK - has placeholder
        x = "hello"        # OK - regular string
    """

    code: ClassVar[str] = "F541"
    message: ClassVar[str] = "f-string without any placeholders"
    _PREFIX_CHAR: ClassVar[str] = "f"


class TStringMissingPlaceholders(_PrefixStringMissingPlaceholders):
    """
    F542: t-string without any placeholders.

    Rationale: A t-string without placeholders adds overhead for no
    benefit. Remove the ``t`` prefix to use a regular string.

    Example::

        # Bad
        x = t"hello"       # F542 - no placeholders

        # Good
        x = t"hello {name}"
        x = "hello"        # plain string
    """

    code: ClassVar[str] = "F542"
    message: ClassVar[str] = "t-string without any placeholders"
    _PREFIX_CHAR: ClassVar[str] = "t"


LITERAL_RULES = [
    FStringMissingPlaceholders,
    TStringMissingPlaceholders,
]

__all__ = [
    "LITERAL_RULES",
    "FStringMissingPlaceholders",
    "TStringMissingPlaceholders",
]
