"""Shared utility functions for rude rules."""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from rude._rust import find_comment_start as find_comment_start

if TYPE_CHECKING:
    from rude.core.node import Node


class ImportAlias(NamedTuple):
    """A single import alias extracted from an import statement."""

    full_name: str
    alias: str | None
    is_from: bool


def iter_import_aliases(node: Node) -> Iterator[ImportAlias]:
    """Yield an ``ImportAlias`` for each alias in an import statement.

    Handles plain imports, from-imports, and ``__future__`` imports transparently.
    For non-import nodes, yields nothing.
    """
    if node.type == "import_statement":
        children = list(node.named_children)
        module: str | None = None
        is_from = False
    elif node.type == "future_import_statement":
        children = list(node.named_children)
        module = "__future__"
        is_from = True
    elif node.type == "import_from_statement":
        children = list(node.named_children)
        if not children:
            return
        first = children[0]
        if first.type == "dotted_name":
            module = first.text
            children = children[1:]
        elif first.type == "relative_import":
            prefix = ""
            mod_inside: str | None = None
            for rc in first.children:
                if rc.type == "import_prefix":
                    prefix = rc.text
                elif rc.type == "dotted_name":
                    mod_inside = rc.text
            module = prefix + (mod_inside or "")
            children = children[1:]
        else:
            return
        is_from = True
    else:
        return

    def _full(name: str) -> str:
        if not module:
            return name
        sep = "" if module.endswith(".") else "."
        return f"{module}{sep}{name}"

    for c in children:
        if c.type == "dotted_name":
            yield ImportAlias(_full(c.text), None, is_from)
        elif c.type == "aliased_import":
            name_node = c.child_by_field("name")
            alias_node = c.child_by_field("alias")
            if name_node is None:
                continue
            alias = alias_node.text if alias_node else None
            yield ImportAlias(_full(name_node.text), alias, is_from)


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write text to a file atomically using a temp file + os.replace."""
    if path.is_symlink():
        raise ValueError(f"Refusing to write through symlink: {path}")
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def extract_string_content(text: str) -> str | None:
    """Extract the content of a string literal, stripping prefix and quotes."""
    if not text:
        return None

    # Strip string prefix characters (f, r, b, u and their uppercase variants)
    i = 0
    while i < len(text) and text[i] in "fFrRbBuUtT":
        i += 1
    content = text[i:]

    # Handle triple-quoted strings
    if content.startswith('"""') or content.startswith("'''"):
        quote = content[:3]
        if content.endswith(quote):
            return content[3:-3]
        return None

    # Handle single-quoted strings
    if content.startswith('"') or content.startswith("'"):
        quote = content[0]
        if content.endswith(quote):
            return content[1:-1]
        return None

    return None
