"""File discovery with gitignore support using fast os.scandir."""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from fnmatch import fnmatch
from pathlib import Path

ALWAYS_SKIP: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".venv",
        "venv",
        ".env",
        "env",
        "node_modules",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        "dist",
        "build",
        ".eggs",
        "*.egg-info",
        ".coverage",
        "htmlcov",
        ".ipynb_checkpoints",
    }
)


def find_python_files(root: Path | str, *, respect_gitignore: bool = True) -> Iterator[Path]:
    """Find all Python files under root directory."""
    root = Path(root).resolve()
    gitignores: list[_GitIgnore] = []
    if respect_gitignore:
        local = _load_gitignore(root)
        if local is not None:
            gitignores.append(local)
    yield from _scan_directory(root, root, gitignores, respect_gitignore=respect_gitignore)


def _matches_any(gitignores: list[_GitIgnore], path: Path, *, is_dir: bool) -> bool:
    for gi in gitignores:
        try:
            rel = str(path.relative_to(gi._root))
        except ValueError:
            continue
        if is_dir:
            rel = rel + "/"
        if gi.match(rel):
            return True
    return False


def _scan_directory(
    directory: Path,
    root: Path,
    gitignores: list[_GitIgnore],
    *,
    respect_gitignore: bool,
) -> Iterator[Path]:
    # Nested .gitignore: load the local one for this directory (root already loaded).
    if respect_gitignore and directory != root:
        local = _load_gitignore(directory)
        if local is not None:
            gitignores = [*gitignores, local]

    try:
        with os.scandir(directory) as entries:
            dirs: list[os.DirEntry[str]] = []
            files: list[os.DirEntry[str]] = []
            for entry in entries:
                (dirs if entry.is_dir(follow_symlinks=False) else files).append(entry)

            for entry in sorted(files, key=lambda e: e.name):
                if not entry.name.endswith(".py"):
                    continue
                path = Path(entry.path)
                if _matches_any(gitignores, path, is_dir=False):
                    continue
                yield path

            for entry in sorted(dirs, key=lambda e: e.name):
                name = entry.name
                if name.startswith(".") or name in ALWAYS_SKIP:
                    continue
                if any(fnmatch(name, p) for p in ALWAYS_SKIP if "*" in p):
                    continue
                dir_path = Path(entry.path)
                if _matches_any(gitignores, dir_path, is_dir=True):
                    continue
                yield from _scan_directory(
                    dir_path, root, gitignores, respect_gitignore=respect_gitignore
                )
    except PermissionError:
        pass


class _GitIgnore:
    def __init__(self, patterns: list[str], root: Path) -> None:
        self._root = root
        self._positive: list[tuple[str, bool]] = []
        self._negated: list[tuple[str, bool]] = []
        for p in patterns:
            p = p.strip()
            if not p or p.startswith("#"):
                continue
            target = self._negated if p.startswith("!") else self._positive
            if p.startswith("!"):
                p = p[1:]
            is_dir_only = p.endswith("/")
            if is_dir_only:
                p = p[:-1]
            target.append((p, is_dir_only))

    def match(self, path: str) -> bool:
        is_dir = path.endswith("/")
        if is_dir:
            path = path[:-1]
        matched = False
        for pattern, dir_only in self._positive:
            if dir_only and not is_dir:
                continue
            if self._match_pattern(pattern, path):
                matched = True
                break
        if matched:
            for pattern, dir_only in self._negated:
                if dir_only and not is_dir:
                    continue
                if self._match_pattern(pattern, path):
                    return False
        return matched

    def _match_pattern(self, pattern: str, path: str) -> bool:
        if "/" in pattern:
            if pattern.startswith("/"):
                pattern = pattern[1:]
            return fnmatch(path, pattern) or fnmatch(path, f"**/{pattern}")
        return any(fnmatch(part, pattern) for part in path.split("/"))


def _load_gitignore(root: Path) -> _GitIgnore | None:
    path = root / ".gitignore"
    if not path.exists():
        return None
    try:
        return _GitIgnore(path.read_text(encoding="utf-8").splitlines(), root)
    except OSError:
        return None


def resolve_paths(paths: Sequence[str | Path]) -> Iterator[Path]:
    """Resolve paths (files or directories) to Python files."""
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        if p.is_file() and p.suffix == ".py":
            yield p
        elif p.is_dir():
            yield from find_python_files(p)


__all__ = ["ALWAYS_SKIP", "find_python_files", "resolve_paths"]
