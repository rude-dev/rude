"""Tests for import rules (E401, E402)."""

from rude.rules.pycodestyle import (
    ModuleLevelImportNotAtTop,
    MultipleImportsOnOneLine,
)
from tests.conftest import check_source


class TestMultipleImportsOnOneLine:
    """Tests for E401: multiple imports on one line."""

    def test_multiple_imports(self):
        source = "import os, sys"
        diagnostics = check_source(MultipleImportsOnOneLine, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E401"

    def test_single_import_ok(self):
        source = "import os"
        diagnostics = check_source(MultipleImportsOnOneLine, source)
        assert len(diagnostics) == 0

    def test_from_import_ok(self):
        source = "from os import path, getcwd"
        diagnostics = check_source(MultipleImportsOnOneLine, source)
        assert len(diagnostics) == 0


class TestModuleLevelImportNotAtTop:
    """Tests for E402: module level import not at top of file."""

    def test_import_after_code(self):
        source = """x = 1
import os"""
        diagnostics = check_source(ModuleLevelImportNotAtTop, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E402"

    def test_import_at_top_ok(self):
        source = """import os
x = 1"""
        diagnostics = check_source(ModuleLevelImportNotAtTop, source)
        assert len(diagnostics) == 0

    def test_import_after_docstring_ok(self):
        source = '''"""Module docstring."""
import os'''
        diagnostics = check_source(ModuleLevelImportNotAtTop, source)
        assert len(diagnostics) == 0

    def test_import_after_future_ok(self):
        source = "from __future__ import annotations\nimport os"
        diagnostics = check_source(ModuleLevelImportNotAtTop, source)
        assert len(diagnostics) == 0
