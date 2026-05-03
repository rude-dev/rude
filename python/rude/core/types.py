"""
Core types for Rude linter.

Defines fundamental data structures: locations, edits, fixes, diagnostics,
and file context with metadata provider support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, Self, TypeVar, cast

if TYPE_CHECKING:
    from rude._rust import LineInfo, TSNode, TSTree
    from rude.core.node import Node


class Severity(Enum):
    """Diagnostic severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


@dataclass(frozen=True, slots=True)
class Location:
    """Source code location (LSP compatible: line 1-indexed, column 0-indexed)."""

    line: int
    column: int
    end_line: int | None = None
    end_column: int | None = None

    @classmethod
    def from_ts_node(cls, node: TSNode) -> Location:
        return cls(
            line=node.start_point[0] + 1,
            column=node.start_point[1],
            end_line=node.end_point[0] + 1,
            end_column=node.end_point[1],
        )

    def __str__(self) -> str:
        if self.end_line is not None and self.end_line != self.line:
            return f"{self.line}:{self.column}-{self.end_line}:{self.end_column}"
        return f"{self.line}:{self.column}"


@dataclass(frozen=True, slots=True)
class Edit:
    """A single text edit operation (byte-based)."""

    start_byte: int
    end_byte: int
    new_text: str


@dataclass(frozen=True, slots=True)
class Fix:
    """
    Autofix for a diagnostic.

    Fixes are declarative - rules describe WHAT should change,
    the linter handles HOW (including import insertion).
    """

    description: str
    edits: tuple[Edit, ...] = ()
    imports_needed: tuple[str, ...] = ()
    imports_from_needed: tuple[tuple[str, str], ...] = ()

    @classmethod
    def replace(
        cls,
        node: Node,
        new_text: str,
        *,
        description: str | None = None,
        imports: list[str] | None = None,
        imports_from: list[tuple[str, str]] | None = None,
    ) -> Fix:
        """Replace a node with new text."""
        desc = description or f"Replace with `{new_text[:50]}{'...' if len(new_text) > 50 else ''}`"
        return cls(
            description=desc,
            edits=(Edit(node.start_byte, node.end_byte, new_text),),
            imports_needed=tuple(imports or ()),
            imports_from_needed=tuple(imports_from or ()),
        )

    @classmethod
    def delete(cls, node: Node, *, description: str | None = None) -> Fix:
        """Delete a node."""
        return cls(
            description=description or "Delete",
            edits=(Edit(node.start_byte, node.end_byte, ""),),
        )

    @classmethod
    def insert_before(
        cls,
        node: Node,
        text: str,
        *,
        description: str | None = None,
        imports: list[str] | None = None,
    ) -> Fix:
        """Insert text before a node."""
        desc = description or f"Insert `{text[:30]}`"
        return cls(
            description=desc,
            edits=(Edit(node.start_byte, node.start_byte, text),),
            imports_needed=tuple(imports or ()),
        )

    @classmethod
    def insert_after(
        cls,
        node: Node,
        text: str,
        *,
        description: str | None = None,
        imports: list[str] | None = None,
    ) -> Fix:
        """Insert text after a node."""
        desc = description or f"Insert `{text[:30]}`"
        return cls(
            description=desc,
            edits=(Edit(node.end_byte, node.end_byte, text),),
            imports_needed=tuple(imports or ()),
        )

    @classmethod
    def add_decorator(
        cls,
        node: Node,
        decorator: str,
        *,
        description: str | None = None,
        imports: list[str] | None = None,
    ) -> Fix:
        """Add a decorator to a function or class."""
        indent = " " * node.column
        text = f"@{decorator}\n{indent}"
        return cls.insert_before(
            node,
            text,
            description=description or f"Add @{decorator}",
            imports=imports,
        )


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A linting diagnostic (error, warning, etc.)."""

    code: str
    message: str
    location: Location
    severity: Severity = Severity.WARNING
    fix: Fix | None = None

    def __str__(self) -> str:
        fixable = " (fixable)" if self.fix else ""
        return f"[{self.code}] {self.message}{fixable}"

    @property
    def is_fixable(self) -> bool:
        return self.fix is not None


@dataclass(frozen=True, slots=True)
class FixResult:
    """Result of applying fixes to source."""

    source: str
    applied: tuple[Diagnostic, ...]
    dropped: tuple[Diagnostic, ...]


# Type for metadata providers


class MetadataProvider(Protocol):
    """Protocol for metadata providers (ParentProvider, ScopeProvider, etc.).

    Each provider computes additional analysis from a FileContext and returns
    itself with the results cached.
    """

    def compute(self, ctx: FileContext) -> Self: ...


MetadataProviderT = TypeVar("MetadataProviderT", bound=MetadataProvider)


@dataclass
class FileContext:
    """
    Context for linting a single file.

    Provides access to source, parsed tree, and metadata providers.
    """

    path: Path
    source: bytes
    tree: TSTree

    _lines: list[bytes] | None = field(default=None, repr=False)
    _text: str | None = field(default=None, repr=False)
    _text_lines: list[str] | None = field(default=None, repr=False)
    _string_lines: frozenset[int] | None = field(default=None, repr=False)
    _noqa_map: dict[int, bool | set[str]] | None = field(default=None, repr=False)
    _line_infos: list[LineInfo] | None = field(default=None, repr=False)
    _metadata_cache: dict[type, object] = field(default_factory=dict, repr=False)

    @property
    def text(self) -> str:
        if self._text is None:
            self._text = self.source.decode("utf-8", errors="replace")
        return self._text

    @property
    def lines(self) -> list[bytes]:
        if self._lines is None:
            self._lines = self.source.splitlines(keepends=True)
        return self._lines

    @property
    def text_lines(self) -> list[str]:
        """Decoded text lines (no trailing newline). Cached."""
        if self._text_lines is None:
            self._text_lines = [
                lb.decode("utf-8", errors="replace").rstrip("\r\n") for lb in self.lines
            ]
        return self._text_lines

    @property
    def string_lines(self) -> frozenset[int]:
        """Line numbers (1-based) inside multi-line strings. Cached."""
        if self._string_lines is None:
            lines: set[int] = set()
            cursor = self.tree.root_node.walk()
            self._walk_string_lines(cursor, lines)
            self._string_lines = frozenset(lines)
        return self._string_lines

    @staticmethod
    def _walk_string_lines(cursor: Any, lines: set[int]) -> None:
        """Walk tree-sitter tree to find multi-line string nodes."""
        if cursor.node.type == "string":
            start_row = cursor.node.start_point[0]  # 0-based
            end_row = cursor.node.end_point[0]
            if end_row > start_row:
                for ln in range(start_row + 2, end_row + 2):
                    lines.add(ln)
            return  # no need to descend into string children
        if cursor.goto_first_child():
            while True:
                FileContext._walk_string_lines(cursor, lines)
                if not cursor.goto_next_sibling():
                    break
            cursor.goto_parent()

    @classmethod
    def from_analysis(
        cls,
        path: Path,
        source: bytes,
        tree: TSTree,
        *,
        string_lines: frozenset[int] | None = None,
        noqa_map: dict[int, bool | set[str]] | None = None,
        line_infos: list[LineInfo] | None = None,
    ) -> FileContext:
        """Create a FileContext with pre-computed analysis results."""
        ctx = cls(path=path, source=source, tree=tree)
        ctx._string_lines = string_lines
        ctx._noqa_map = noqa_map
        ctx._line_infos = line_infos
        return ctx

    def get_line(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].decode("utf-8", errors="replace")
        return ""

    @cached_property
    def _line_offsets(self) -> list[int]:
        """Prefix-sum of line lengths for O(1) byte-offset lookups."""
        offsets = [0]
        for line in self.lines:
            offsets.append(offsets[-1] + len(line))
        return offsets

    def line_start_byte(self, lineno: int) -> int:
        """Byte offset of the start of the given 1-based line."""
        return self._line_offsets[lineno - 1]

    def get_node_text(self, node: TSNode) -> str:
        return self.source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def is_test_file(self) -> bool:
        path_str = str(self.path)
        name = self.path.name
        return (
            "/tests/" in path_str
            or "/test/" in path_str
            or name.startswith("test_")
            or name.endswith("_test.py")
        )

    def is_in_path(self, *patterns: str) -> bool:
        path_str = self.path.as_posix()
        return any(p in path_str for p in patterns)

    def has_noqa(self, line: int, code: str | None = None) -> bool:
        """Check if line has a noqa comment suppressing this diagnostic."""
        if self._noqa_map is not None:
            entry = self._noqa_map.get(line)
            if entry is None:
                return False
            if entry is True:
                return True  # Blanket noqa
            assert isinstance(entry, set)
            return code is None or code in entry
        # Fallback for non-batch path (no pre-built map)
        import re

        line_text = self.get_line(line)
        if "# noqa" not in line_text.lower():
            return False
        match = re.search(r"#\s*noqa\s*(?::\s*([A-Z0-9,\s]+))?", line_text, re.IGNORECASE)
        if not match:
            return False
        codes_str = match.group(1)
        if not codes_str:
            return True  # Blanket noqa
        if code is None:
            return True
        codes = [c.strip().upper() for c in codes_str.split(",")]
        return code.upper() in codes

    def get_metadata(self, provider_cls: type[MetadataProviderT]) -> MetadataProviderT:
        """Get metadata from a provider (lazy computed and cached)."""
        if provider_cls not in self._metadata_cache:
            provider: Any = provider_cls()
            self._metadata_cache[provider_cls] = provider.compute(self)
        return cast(MetadataProviderT, self._metadata_cache[provider_cls])

    def set_metadata(self, provider_cls: type[MetadataProviderT], value: MetadataProviderT) -> None:
        """Inject a pre-computed metadata provider into the cache."""
        self._metadata_cache[provider_cls] = value


__all__ = [
    "Diagnostic",
    "Edit",
    "FileContext",
    "Fix",
    "FixResult",
    "Location",
    "MetadataProvider",
    "MetadataProviderT",
    "Severity",
]
