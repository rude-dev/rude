"""End-to-end tests for # noqa suppression."""

from rude import Linter
from rude.rules.pyflakes import UnusedImport


def _make_linter() -> Linter:
    linter = Linter()
    linter.register(UnusedImport())
    return linter


def test_noqa_blanket_suppresses():
    """A blanket # noqa suppresses all diagnostics on that line."""
    source = "import os  # noqa\n"
    diags = list(_make_linter().check_source(source))
    assert len(diags) == 0


def test_noqa_specific_code_suppresses():
    """# noqa: F401 suppresses F401 specifically."""
    source = "import os  # noqa: F401\n"
    diags = list(_make_linter().check_source(source))
    assert len(diags) == 0


def test_noqa_wrong_code_does_not_suppress():
    """# noqa: E711 does not suppress F401."""
    source = "import os  # noqa: E711\n"
    diags = list(_make_linter().check_source(source))
    assert len(diags) == 1
    assert diags[0].code == "F401"


def test_no_noqa_produces_diagnostic():
    """Without # noqa, the diagnostic is emitted."""
    source = "import os\n"
    diags = list(_make_linter().check_source(source))
    assert len(diags) == 1
    assert diags[0].code == "F401"
