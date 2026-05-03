"""Shared utility functions for rude rules."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from rude._rust import find_comment_start as find_comment_start


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
