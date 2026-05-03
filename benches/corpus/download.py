#!/usr/bin/env python3
"""Download real-world Python projects for benchmarking.

Usage:
    uv run python benches/corpus/download.py         # download all
    uv run python benches/corpus/download.py large    # download one
    uv run python benches/corpus/download.py --force  # re-download
"""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path
from urllib.request import urlopen

CORPUS_DIR = Path(__file__).parent

PROJECTS = {
    "large": {
        "name": "django",
        "url": "https://github.com/django/django/archive/refs/heads/main.zip",
        "subdir": "django-main/django",
    },
    "huge": {
        "name": "homeassistant",
        "url": "https://github.com/home-assistant/core/archive/refs/heads/dev.zip",
        "subdir": "core-dev/homeassistant",
    },
}


def download_project(size: str, *, force: bool = False) -> Path:
    """Download a project corpus."""
    project = PROJECTS[size]
    dest = CORPUS_DIR / size

    if dest.exists() and not force:
        count = len(list(dest.glob("**/*.py")))
        print(f"  {size}: already exists ({count} files)")
        return dest

    print(f"  {size}: downloading {project['name']}...")

    with urlopen(project["url"]) as response:
        data = response.read()

    temp_dir = CORPUS_DIR / f".temp_{size}"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            subdir = project["subdir"]

            if temp_dir.exists():
                shutil.rmtree(temp_dir)

            for member in zf.namelist():
                if member.startswith(subdir):
                    zf.extract(member, temp_dir)

            extracted = temp_dir / subdir
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(extracted), str(dest))
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

    files = len(list(dest.glob("**/*.py")))
    loc = sum(
        len(f.read_text(errors="ignore").splitlines())
        for f in dest.glob("**/*.py")
    )
    print(f"  {size}: {project['name']} ({files} files, {loc:,} LOC)")
    return dest


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Download benchmark corpus")
    parser.add_argument("--force", "-f", action="store_true")
    parser.add_argument(
        "sizes",
        nargs="*",
        choices=[*PROJECTS, "all"],
        default=["all"],
    )
    args = parser.parse_args()

    sizes = list(PROJECTS) if "all" in args.sizes else args.sizes

    print("Downloading benchmark corpus...")
    for size in sizes:
        download_project(size, force=args.force)
    print("Done!")


if __name__ == "__main__":
    main()
