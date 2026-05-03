#!/usr/bin/env python3
"""Check version consistency across pyproject.toml, __init__.py, and Cargo.toml.

Python PEP 440 versions (e.g. `0.1a2`, `0.1.0rc1`) are normalized to the
Rust/Cargo SemVer pre-release format (`0.1.0-alpha.2`, `0.1.0-rc.1`) before
comparison with Cargo.toml. Optionally also validates against a git tag.

Usage:
    python scripts/check_version_consistency.py [--tag TAG]
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PRE_TYPE_MAP = {"a": "alpha", "b": "beta", "rc": "rc"}

PY_VERSION_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?"
    r"(?:(?P<pre_type>a|b|rc)(?P<pre_num>\d+))?$"
)


def read_pyproject_version() -> str:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    return data["project"]["version"]


def read_init_version() -> str:
    text = (REPO_ROOT / "python" / "rude" / "__init__.py").read_text()
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise ValueError("Could not find __version__ in python/rude/__init__.py")
    return match.group(1)


def read_cargo_version() -> str:
    data = tomllib.loads((REPO_ROOT / "Cargo.toml").read_text())
    return data["package"]["version"]


def py_to_cargo(py_version: str) -> str:
    """Convert PEP 440 version to Cargo SemVer pre-release format.

    Examples:
        0.1a2      -> 0.1.0-alpha.2
        0.1.0a2    -> 0.1.0-alpha.2
        0.1rc1     -> 0.1.0-rc.1
        0.1.0      -> 0.1.0
    """
    match = PY_VERSION_RE.match(py_version)
    if not match:
        raise ValueError(f"Cannot parse PEP 440 version: {py_version}")
    major = match.group("major")
    minor = match.group("minor")
    patch = match.group("patch") or "0"
    pre_type = match.group("pre_type")
    pre_num = match.group("pre_num")
    base = f"{major}.{minor}.{patch}"
    if pre_type is None:
        return base
    return f"{base}-{PRE_TYPE_MAP[pre_type]}.{pre_num}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Optional git tag to also validate against pyproject version")
    args = parser.parse_args()

    py_ver = read_pyproject_version()
    init_ver = read_init_version()
    cargo_ver = read_cargo_version()
    expected_cargo = py_to_cargo(py_ver)

    print(f"pyproject.toml      : {py_ver}")
    print(f"__init__.py         : {init_ver}")
    print(f"Cargo.toml          : {cargo_ver}")
    print(f"Expected Cargo (from Python): {expected_cargo}")
    if args.tag is not None:
        print(f"Git tag             : {args.tag}")

    errors: list[str] = []
    if py_ver != init_ver:
        errors.append(f"pyproject.toml ({py_ver}) != __init__.py ({init_ver})")
    if cargo_ver != expected_cargo:
        errors.append(
            f"Cargo.toml ({cargo_ver}) does not match Python-derived SemVer ({expected_cargo})"
        )
    if args.tag is not None and args.tag != py_ver:
        errors.append(f"Git tag ({args.tag}) != pyproject.toml ({py_ver})")

    if errors:
        print()
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print()
    print("All version strings are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
