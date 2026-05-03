"""Tests for import merging."""

from __future__ import annotations

from pathlib import Path

from rude.core.import_edits import ImportInserter, compute_merged_import_edits
from rude.core.parser import parse
from rude.core.types import FileContext, Fix


def _ctx(source: str) -> FileContext:
    """Create a FileContext from source string."""
    src = source.encode("utf-8")
    return FileContext(path=Path("<test>"), source=src, tree=parse(src))


class TestImportMerging:
    def test_already_imported_no_edit(self):
        ctx = _ctx("import os\n\nx = 1\n")
        fixes = [Fix(description="x", imports_needed=("os",))]
        edits = compute_merged_import_edits(ctx, fixes)
        assert edits == []

    def test_from_import_already_present_no_edit(self):
        ctx = _ctx("from os.path import join\n\nx = 1\n")
        fixes = [Fix(description="x", imports_from_needed=(("os.path", "join"),))]
        edits = compute_merged_import_edits(ctx, fixes)
        assert edits == []

    def test_two_from_imports_same_module_merged(self):
        ctx = _ctx("x = 1\n")
        fixes = [
            Fix(description="a", imports_from_needed=(("typing", "Optional"),)),
            Fix(description="b", imports_from_needed=(("typing", "List"),)),
        ]
        edits = compute_merged_import_edits(ctx, fixes)
        assert len(edits) == 1
        # Names sorted alphabetically
        assert "from typing import List, Optional" in edits[0].new_text

    def test_duplicate_names_deduped(self):
        ctx = _ctx("x = 1\n")
        fixes = [
            Fix(description="a", imports_from_needed=(("typing", "Optional"),)),
            Fix(description="b", imports_from_needed=(("typing", "Optional"),)),
        ]
        edits = compute_merged_import_edits(ctx, fixes)
        assert len(edits) == 1
        assert edits[0].new_text.count("Optional") == 1

    def test_insert_after_future_has_blank_line(self):
        ctx = _ctx("from __future__ import annotations\n\nx = 1\n")
        fixes = [Fix(description="x", imports_needed=("os",))]
        edits = compute_merged_import_edits(ctx, fixes)
        assert len(edits) == 1
        assert edits[0].new_text.startswith("\n")

    def test_different_modules_separate_edits(self):
        ctx = _ctx("x = 1\n")
        fixes = [
            Fix(description="a", imports_from_needed=(("typing", "Optional"),)),
            Fix(description="b", imports_needed=("os",)),
        ]
        edits = compute_merged_import_edits(ctx, fixes)
        assert len(edits) == 2


class TestMergedFromImportEdit:
    def test_filters_already_imported(self):
        ctx = _ctx("from typing import Optional\n\nx = 1\n")
        inserter = ImportInserter(ctx)
        edit = inserter.get_merged_from_import_edit("typing", ["Optional", "List"])
        assert edit is not None
        assert "List" in edit.new_text
        assert "Optional" not in edit.new_text

    def test_all_already_imported_returns_none(self):
        ctx = _ctx("from typing import Optional, List\n\nx = 1\n")
        inserter = ImportInserter(ctx)
        edit = inserter.get_merged_from_import_edit("typing", ["Optional", "List"])
        assert edit is None

    def test_names_sorted(self):
        ctx = _ctx("x = 1\n")
        inserter = ImportInserter(ctx)
        edit = inserter.get_merged_from_import_edit("typing", ["Zebra", "Alpha", "Mid"])
        assert edit is not None
        assert "Alpha, Mid, Zebra" in edit.new_text
