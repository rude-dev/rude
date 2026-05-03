"""Tests for the fix engine (_apply_fixes)."""

from __future__ import annotations

from rude.core.linter import Linter
from rude.core.types import Diagnostic, Edit, Fix, Location, Severity


def _make_diag(code: str, line: int, col: int, fix: Fix | None = None) -> Diagnostic:
    """Create a diagnostic for testing."""
    return Diagnostic(
        code=code,
        message=f"test {code}",
        location=Location(line=line, column=col),
        severity=Severity.WARNING,
        fix=fix,
    )


def _apply(
    source: str, diagnostics: list[Diagnostic]
) -> tuple[tuple[Diagnostic, ...], tuple[Diagnostic, ...], str]:
    """Apply fixes and return (applied, dropped, result_source)."""
    from pathlib import Path

    from rude.core.parser import parse
    from rude.core.types import FileContext

    source_bytes = source.encode("utf-8")
    tree = parse(source_bytes)
    ctx = FileContext(path=Path("<test>"), source=source_bytes, tree=tree)

    linter = Linter()
    result = linter._apply_fixes(ctx, diagnostics)
    return result.applied, result.dropped, result.source


class TestOverlap:
    def test_non_overlapping_all_applied(self):
        source = "aaa bbb ccc\n"
        d1 = _make_diag("T1", 1, 0, Fix(description="x", edits=(Edit(0, 3, "AAA"),)))
        d2 = _make_diag("T2", 1, 8, Fix(description="x", edits=(Edit(8, 11, "CCC"),)))
        applied, dropped, result = _apply(source, [d1, d2])
        assert result == "AAA bbb CCC\n"
        assert len(applied) == 2
        assert len(dropped) == 0

    def test_overlapping_first_in_file_wins(self):
        source = "abcdefgh\n"
        d1 = _make_diag("T1", 1, 0, Fix(description="x", edits=(Edit(0, 5, "XXXXX"),)))
        d2 = _make_diag("T2", 1, 3, Fix(description="x", edits=(Edit(3, 8, "YYYYY"),)))
        applied, dropped, result = _apply(source, [d1, d2])
        assert result == "XXXXXfgh\n"
        assert len(applied) == 1
        assert applied[0].code == "T1"
        assert len(dropped) == 1
        assert dropped[0].code == "T2"

    def test_adjacent_edits_both_applied(self):
        source = "aabbcc\n"
        d1 = _make_diag("T1", 1, 0, Fix(description="x", edits=(Edit(0, 2, "AA"),)))
        d2 = _make_diag("T2", 1, 2, Fix(description="x", edits=(Edit(2, 4, "BB"),)))
        applied, _, result = _apply(source, [d1, d2])
        assert result == "AABBcc\n"
        assert len(applied) == 2

    def test_two_inserts_same_position_both_applied(self):
        source = "hello\n"
        d1 = _make_diag("T1", 1, 0, Fix(description="x", edits=(Edit(0, 0, "A"),)))
        d2 = _make_diag("T2", 1, 0, Fix(description="x", edits=(Edit(0, 0, "B"),)))
        applied, _, result = _apply(source, [d1, d2])
        assert len(applied) == 2
        # Both inserts at position 0; order depends on sort stability
        assert "hello" in result
        assert "A" in result
        assert "B" in result


class TestAtomicity:
    def test_multi_edit_fix_all_or_nothing(self):
        source = "aaa bbb ccc\n"
        # d1 replaces "aaa" and "ccc"
        d1 = _make_diag(
            "T1",
            1,
            0,
            Fix(
                description="x",
                edits=(Edit(0, 3, "AAA"), Edit(8, 11, "CCC")),
            ),
        )
        # d2 overlaps with d1's second edit
        d2 = _make_diag("T2", 1, 6, Fix(description="x", edits=(Edit(6, 9, "XXX"),)))
        applied, _, result = _apply(source, [d1, d2])
        # d1 accepted first (starts at byte 0), d2 dropped (overlaps byte 8-11)
        assert result == "AAA bbb CCC\n"
        assert len(applied) == 1
        assert applied[0].code == "T1"

    def test_multi_edit_conflict_drops_entire_fix(self):
        source = "aaa bbb ccc\n"
        # d1 replaces "bbb"
        d1 = _make_diag("T1", 1, 4, Fix(description="x", edits=(Edit(4, 7, "BBB"),)))
        # d2 has two edits: one at "aaa" (ok) and one overlapping "bbb" (conflict)
        d2 = _make_diag(
            "T2",
            1,
            0,
            Fix(
                description="x",
                edits=(Edit(0, 3, "AAA"), Edit(5, 6, "X")),
            ),
        )
        # d2 sorted first (byte 0), accepted. d1 (byte 4) conflicts with d2's edit at 5-6.
        applied, _, _ = _apply(source, [d2, d1])
        assert len(applied) == 1
        assert applied[0].code == "T2"


class TestFixApplication:
    def test_single_replace(self):
        source = "old\n"
        d = _make_diag("T1", 1, 0, Fix(description="x", edits=(Edit(0, 3, "new"),)))
        _, _, result = _apply(source, [d])
        assert result == "new\n"

    def test_single_delete(self):
        source = "hello world\n"
        d = _make_diag("T1", 1, 5, Fix(description="x", edits=(Edit(5, 11, ""),)))
        _, _, result = _apply(source, [d])
        assert result == "hello\n"

    def test_single_insert(self):
        source = "helloworld\n"
        d = _make_diag("T1", 1, 5, Fix(description="x", edits=(Edit(5, 5, " "),)))
        _, _, result = _apply(source, [d])
        assert result == "hello world\n"


class TestFixResult:
    def test_applied_count(self):
        source = "aaa bbb\n"
        d1 = _make_diag("T1", 1, 0, Fix(description="x", edits=(Edit(0, 3, "AAA"),)))
        d2 = _make_diag("T2", 1, 4, Fix(description="x", edits=(Edit(4, 7, "BBB"),)))
        applied, dropped, _ = _apply(source, [d1, d2])
        assert len(applied) == 2
        assert len(dropped) == 0

    def test_dropped_count(self):
        source = "abcdef\n"
        d1 = _make_diag("T1", 1, 0, Fix(description="x", edits=(Edit(0, 4, "XXXX"),)))
        d2 = _make_diag("T2", 1, 2, Fix(description="x", edits=(Edit(2, 6, "YYYY"),)))
        applied, dropped, _ = _apply(source, [d1, d2])
        assert len(applied) == 1
        assert len(dropped) == 1
