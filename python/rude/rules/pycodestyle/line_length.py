"""
Line length rules: E501.

E501: line too long
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic

if TYPE_CHECKING:
    from rude.core.node import Node


class LineTooLong(Rule):
    """
    E501: Line too long.

    Rationale: PEP 8 recommends a maximum line length of 79 characters
    for readability and side-by-side diff viewing.

    Example::

        # Bad
        x = "this is a very long line that exceeds the maximum line length limit"  # E501

        # Good
        x = (
            "this is a long line that has been"
            " wrapped for readability"
        )

    Configuration:
        [tool.rude.rules.E501]
        max_line_length = 79  # default
    """

    code: ClassVar[str] = "E501"
    message: ClassVar[str] = "line too long ({length} > {max_length} characters)"
    node_types = {NodeType.MODULE}

    max_line_length: int = 79

    def configure(self, options: dict[str, Any]) -> None:
        self.max_line_length = options.get("max_line_length", 79)

    def check(self, node: Node) -> Iterator[Diagnostic]:
        # Only run once at module level
        if node.parent is not None:
            return

        ctx = node.ctx
        max_len = self.max_line_length
        line_infos = ctx._line_infos

        if line_infos is not None:
            # Fast path: use pre-computed byte length from Rust.
            # byte_len >= char_len for UTF-8, so byte_len <= max skips safely.
            for lineno_0, info in enumerate(line_infos):
                byte_len = info.line_len
                if byte_len <= max_len:
                    continue

                # Byte length exceeded — decode to get true character length
                line = ctx.lines[lineno_0].decode("utf-8", errors="replace")
                length = len(line.rstrip("\r\n"))
                if length <= max_len:
                    continue

                lineno = lineno_0 + 1

                # Skip lines that are mostly URLs
                stripped = line.strip()
                if self._is_url_line(stripped):
                    continue

                # Skip noqa lines
                if ctx.has_noqa(lineno, self.code):
                    continue

                yield self.diagnostic_at(
                    lineno,
                    max_len,
                    self.message.format(length=length, max_length=max_len),
                )
        else:
            # Fallback: decode every line
            for lineno, line_bytes in enumerate(ctx.lines, 1):
                line = line_bytes.decode("utf-8", errors="replace")
                length = len(line.rstrip("\r\n"))

                if length > max_len:
                    # Skip lines that are mostly URLs
                    stripped = line.strip()
                    if self._is_url_line(stripped):
                        continue

                    # Skip noqa lines
                    if ctx.has_noqa(lineno, self.code):
                        continue

                    yield self.diagnostic_at(
                        lineno,
                        max_len,
                        self.message.format(length=length, max_length=max_len),
                    )

    def _is_url_line(self, line: str) -> bool:
        """Check if line is mostly a URL (common exception)."""
        # If line contains a URL and is mostly that URL, skip
        url_prefixes = ("http://", "https://", "ftp://", "file://")
        for prefix in url_prefixes:
            if prefix in line:
                # URL makes up significant portion of the line
                url_start = line.find(prefix)
                url_part = (
                    line[url_start:].split()[0] if line[url_start:].split() else line[url_start:]
                )
                if len(url_part) > self.max_line_length * 0.5:
                    return True
        return False


LINE_LENGTH_RULES = [
    LineTooLong,
]

__all__ = [
    "LINE_LENGTH_RULES",
    "LineTooLong",
]
