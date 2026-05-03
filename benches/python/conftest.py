from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

CORPUS_DIR = Path(__file__).parent.parent / "corpus"


@pytest.fixture
def corpus_large() -> list[Path]:
    d = CORPUS_DIR / "large"
    if not d.exists():
        pytest.skip("Corpus not found (run: uv run python benches/corpus/download.py large)")
    return sorted(d.glob("**/*.py"))


@pytest.fixture
def default_linter() -> Any:
    from rude.core.linter import Linter
    from rude.rules import ALL_RULES

    linter = Linter()
    linter.register_all([cls() for cls in ALL_RULES])
    return linter
