"""Tree-sitter parser for Python."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rude._rust import parse_python
from rude.core.types import FileContext

if TYPE_CHECKING:
    from rude._rust import TSTree


def parse(source: bytes) -> TSTree:
    """Parse Python source bytes into a tree-sitter tree."""
    return parse_python(source)


def parse_string(source: str) -> TSTree:
    """Parse a Python source string into a tree-sitter tree."""
    return parse_python(source.encode("utf-8"))


def parse_file(path: Path | str) -> FileContext:
    """Parse a Python file and return a FileContext."""
    path = Path(path)
    source = path.read_bytes()
    tree = parse_python(source)
    return FileContext(path=path, source=source, tree=tree)


__all__ = ["parse", "parse_file", "parse_string"]
