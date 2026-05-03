"""Tests for the multiprocessing path (_check_files_multiprocess).

The multiprocessing path is used when workers > 1 in check_paths_parallel.
It serializes rule configs, distributes files via LPT scheduling, and
collects results from worker subprocesses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rude.core.linter import CheckOptions, Linter, _resolve_workers, _split_lpt
from rude.core.rule_discovery import discover_rules
from rude.core.types import Diagnostic


def _make_linter(select: list[str]) -> Linter:
    """Build a Linter with the given rule selection."""
    linter = Linter()
    rules = discover_rules(select=select)
    linter.register_all(rules)
    return linter


def _write_test_files(tmp_path: Path) -> dict[str, Path]:
    """Create test files with known violations.

    Returns a mapping of logical name -> path.
    """
    files = {}

    # Clean file -- no diagnostics expected
    p = tmp_path / "clean.py"
    p.write_text("x = 1\ny = x + 2\n")
    files["clean"] = p

    # E711: comparison to None
    p = tmp_path / "comparison.py"
    p.write_text("x = None\nif x == None:\n    pass\n")
    files["comparison"] = p

    # F401: unused import
    p = tmp_path / "unused_import.py"
    p.write_text("import os\n\n\ndef f():\n    pass\n")
    files["unused_import"] = p

    # E401: multiple imports on one line
    p = tmp_path / "multi_import.py"
    p.write_text("import os, sys\n\n\nprint(os.getcwd(), sys.argv)\n")
    files["multi_import"] = p

    # Multiple violations in one file
    p = tmp_path / "mixed.py"
    p.write_text("import json\n\nx = None\nif x == None:\n    pass\n")
    files["mixed"] = p

    # Another clean file
    p = tmp_path / "clean2.py"
    p.write_text("def greet(name):\n    return f'hello {name}'\n")
    files["clean2"] = p

    return files


# ---------------------------------------------------------------------------
# Parity: multiprocess must match streaming
# ---------------------------------------------------------------------------


class TestMultiprocessMatchesStreaming:
    """The most important property: workers=1 and workers=2 must agree."""

    @pytest.mark.slow
    def test_diagnostic_codes_match(self, tmp_path: Path) -> None:
        """Multiprocess and streaming paths produce identical diagnostic codes."""
        files = _write_test_files(tmp_path)
        linter = _make_linter(select=["E711", "F401", "E401"])
        paths = [str(p) for p in files.values()]

        streaming = list(
            linter.check_paths_parallel(
                paths, options=CheckOptions(workers=1), already_resolved=True
            )
        )
        multiprocess = list(
            linter.check_paths_parallel(
                paths, options=CheckOptions(workers=2), already_resolved=True
            )
        )

        streaming_codes = sorted(d.code for _, d in streaming)
        mp_codes = sorted(d.code for _, d in multiprocess)
        assert streaming_codes == mp_codes

    @pytest.mark.slow
    def test_diagnostic_locations_match(self, tmp_path: Path) -> None:
        """Multiprocess and streaming paths produce identical locations."""
        files = _write_test_files(tmp_path)
        linter = _make_linter(select=["E711", "F401"])
        paths = [str(p) for p in files.values()]

        streaming = list(
            linter.check_paths_parallel(
                paths, options=CheckOptions(workers=1), already_resolved=True
            )
        )
        multiprocess = list(
            linter.check_paths_parallel(
                paths, options=CheckOptions(workers=2), already_resolved=True
            )
        )

        def key(item: tuple[Path, Diagnostic]) -> tuple[str, str, int, int]:
            path, d = item
            return (str(path), d.code, d.location.line, d.location.column)

        assert sorted(streaming, key=key) == sorted(multiprocess, key=key)

    @pytest.mark.slow
    def test_messages_match(self, tmp_path: Path) -> None:
        """Multiprocess and streaming paths produce identical messages."""
        files = _write_test_files(tmp_path)
        linter = _make_linter(select=["E711", "F401"])
        paths = [str(p) for p in files.values()]

        streaming = list(
            linter.check_paths_parallel(
                paths, options=CheckOptions(workers=1), already_resolved=True
            )
        )
        multiprocess = list(
            linter.check_paths_parallel(
                paths, options=CheckOptions(workers=2), already_resolved=True
            )
        )

        def key(item: tuple[Path, Diagnostic]) -> tuple[str, str, int, int]:
            path, d = item
            return (str(path), d.code, d.location.line, d.location.column)

        s_sorted = sorted(streaming, key=key)
        m_sorted = sorted(multiprocess, key=key)
        for (sp, sd), (_, md) in zip(s_sorted, m_sorted, strict=True):
            assert sd.message == md.message, (
                f"Message mismatch for {sd.code} at {sp}:{sd.location.line}: "
                f"{sd.message!r} != {md.message!r}"
            )

    @pytest.mark.slow
    def test_parity_with_line_rules(self, tmp_path: Path) -> None:
        """Line rules (W291) also produce identical results across paths."""
        f = tmp_path / "trailing.py"
        # E711: == None, W291: trailing whitespace
        f.write_text("x = 1   \ny = 2\nz = 3  \n")

        linter = _make_linter(select=["W291"])
        paths = [str(f)]

        streaming = list(
            linter.check_paths_parallel(
                paths, options=CheckOptions(workers=1), already_resolved=True
            )
        )
        multiprocess = list(
            linter.check_paths_parallel(
                paths, options=CheckOptions(workers=2), already_resolved=True
            )
        )

        streaming_codes = sorted((str(p), d.code, d.location.line) for p, d in streaming)
        mp_codes = sorted((str(p), d.code, d.location.line) for p, d in multiprocess)
        assert streaming_codes == mp_codes


# ---------------------------------------------------------------------------
# All files processed
# ---------------------------------------------------------------------------


class TestMultiprocessProcessesAllFiles:
    """Every file must be checked -- no silent drops."""

    @pytest.mark.slow
    def test_all_violation_files_appear(self, tmp_path: Path) -> None:
        """Each file with violations appears at least once in output."""
        files = _write_test_files(tmp_path)
        linter = _make_linter(select=["E711", "F401", "E401"])
        paths = [str(p) for p in files.values()]

        diags = list(
            linter.check_paths_parallel(
                paths, options=CheckOptions(workers=2), already_resolved=True
            )
        )

        files_with_diags = {str(p) for p, _ in diags}
        assert str(files["comparison"]) in files_with_diags
        assert str(files["unused_import"]) in files_with_diags
        assert str(files["multi_import"]) in files_with_diags
        assert str(files["mixed"]) in files_with_diags

    @pytest.mark.slow
    def test_clean_files_produce_no_diags(self, tmp_path: Path) -> None:
        """Clean files should not appear in diagnostic output."""
        files = _write_test_files(tmp_path)
        linter = _make_linter(select=["E711", "F401", "E401"])
        paths = [str(p) for p in files.values()]

        diags = list(
            linter.check_paths_parallel(
                paths, options=CheckOptions(workers=2), already_resolved=True
            )
        )

        files_with_diags = {str(p) for p, _ in diags}
        assert str(files["clean"]) not in files_with_diags
        assert str(files["clean2"]) not in files_with_diags

    @pytest.mark.slow
    def test_many_files_across_workers(self, tmp_path: Path) -> None:
        """Create 8 files and verify all are checked with 3 workers."""
        paths = []
        for i in range(8):
            p = tmp_path / f"file_{i}.py"
            p.write_text(f"x_{i} = None\nif x_{i} == None:\n    pass\n")
            paths.append(str(p))

        linter = _make_linter(select=["E711"])
        diags = list(
            linter.check_paths_parallel(
                paths, options=CheckOptions(workers=3), already_resolved=True
            )
        )

        # Each file should produce exactly one E711
        files_seen = {str(fp) for fp, _ in diags}
        for path_str in paths:
            assert path_str in files_seen, f"Missing diagnostics for {path_str}"
        assert len(diags) == 8


# ---------------------------------------------------------------------------
# Rule configuration survives serialization
# ---------------------------------------------------------------------------


class TestRuleConfigInWorker:
    """Rule options must survive the serialization round-trip to workers."""

    @pytest.mark.slow
    def test_configured_rule_applied_in_worker(self, tmp_path: Path) -> None:
        """F841 with custom ignore_prefixes is respected in workers."""
        # This file has an unused variable 'tmp_count' which would be flagged
        # with default config but should be ignored with ignore_prefixes=["_", "tmp_"]
        f = tmp_path / "configured.py"
        f.write_text("def foo():\n    tmp_count = 1\n    x = 2\n    return x\n")

        # Default config: tmp_count IS flagged
        from rude.rules.pyflakes import UnusedVariable

        linter_default = Linter()
        linter_default.register(UnusedVariable())

        default_diags = list(
            linter_default.check_paths_parallel(
                [str(f)], options=CheckOptions(workers=2), already_resolved=True
            )
        )
        default_names = {d.message for _, d in default_diags}
        assert any("tmp_count" in m for m in default_names), (
            "Precondition: tmp_count should be flagged with default config"
        )

        # Custom config: tmp_count should be suppressed
        rule = UnusedVariable()
        rule.configure({"ignore_prefixes": ["_", "tmp_"]})

        linter_custom = Linter()
        linter_custom.register(rule)

        custom_diags = list(
            linter_custom.check_paths_parallel(
                [str(f)], options=CheckOptions(workers=2), already_resolved=True
            )
        )
        custom_names = {d.message for _, d in custom_diags}
        assert not any("tmp_count" in m for m in custom_names), (
            "tmp_count should be suppressed with ignore_prefixes=['_', 'tmp_']"
        )


# ---------------------------------------------------------------------------
# Mixed rule types (AST + Line)
# ---------------------------------------------------------------------------


class TestMultiprocessMixedRules:
    """Both AST rules and line rules work through multiprocessing."""

    @pytest.mark.slow
    def test_ast_and_line_rules_combined(self, tmp_path: Path) -> None:
        """AST rule (E711) and line rule (W291) both fire in multiprocess."""
        f = tmp_path / "both.py"
        # E711: == None, W291: trailing whitespace
        f.write_text("x = None   \nif x == None:\n    pass\n")

        linter = _make_linter(select=["E711", "W291"])
        diags = list(
            linter.check_paths_parallel(
                [str(f)], options=CheckOptions(workers=2), already_resolved=True
            )
        )

        codes = {d.code for _, d in diags}
        assert "E711" in codes, "AST rule E711 should fire"
        assert "W291" in codes, "Line rule W291 should fire"


# ---------------------------------------------------------------------------
# Empty and single-file edge cases
# ---------------------------------------------------------------------------


class TestMultiprocessEdgeCases:
    """Edge cases for the multiprocessing path."""

    def test_empty_file_list(self) -> None:
        """Empty file list produces no diagnostics (never enters multiprocess)."""
        linter = _make_linter(select=["E711"])
        diags = list(
            linter.check_paths_parallel([], options=CheckOptions(workers=2), already_resolved=True)
        )
        assert diags == []

    @pytest.mark.slow
    def test_single_file_with_workers_2(self, tmp_path: Path) -> None:
        """A single file with workers=2 still works (1 worker gets empty chunk)."""
        f = tmp_path / "solo.py"
        f.write_text("x = None\nif x == None:\n    pass\n")

        linter = _make_linter(select=["E711"])
        diags = list(
            linter.check_paths_parallel(
                [str(f)], options=CheckOptions(workers=2), already_resolved=True
            )
        )

        codes = [d.code for _, d in diags]
        assert "E711" in codes

    @pytest.mark.slow
    def test_single_clean_file(self, tmp_path: Path) -> None:
        """A single clean file produces no diagnostics in multiprocess."""
        f = tmp_path / "ok.py"
        f.write_text("x = 1\n")

        linter = _make_linter(select=["E711", "F401"])
        diags = list(
            linter.check_paths_parallel(
                [str(f)], options=CheckOptions(workers=2), already_resolved=True
            )
        )
        assert diags == []

    @pytest.mark.slow
    def test_syntax_error_in_multiprocess(self, tmp_path: Path) -> None:
        """A file with syntax error produces E999 through multiprocessing."""
        broken = tmp_path / "broken.py"
        broken.write_text("def f(\n")
        good = tmp_path / "good.py"
        good.write_text("x = None\nif x == None:\n    pass\n")

        linter = _make_linter(select=["E711"])
        diags = list(
            linter.check_paths_parallel(
                [str(broken), str(good)], options=CheckOptions(workers=2), already_resolved=True
            )
        )

        codes = {d.code for _, d in diags}
        assert "E999" in codes, "Syntax error should produce E999"
        assert "E711" in codes, "Good file should still be checked"


# ---------------------------------------------------------------------------
# LPT scheduling
# ---------------------------------------------------------------------------


class TestSplitLPT:
    """Unit tests for _split_lpt (Longest Processing Time scheduling)."""

    def test_even_split(self, tmp_path: Path) -> None:
        """4 equal-size files split into 2 chunks of 2."""
        paths = []
        for i in range(4):
            p = tmp_path / f"f{i}.py"
            p.write_text("x" * 100)
            paths.append(p)

        chunks = _split_lpt(paths, 2)
        assert len(chunks) == 2
        total = sum(len(c) for c in chunks)
        assert total == 4

    def test_more_workers_than_files(self, tmp_path: Path) -> None:
        """2 files with 4 workers: only 2 non-empty chunks."""
        paths = []
        for i in range(2):
            p = tmp_path / f"f{i}.py"
            p.write_text("x" * 100)
            paths.append(p)

        chunks = _split_lpt(paths, 4)
        # _split_lpt filters empty chunks
        assert len(chunks) == 2
        total = sum(len(c) for c in chunks)
        assert total == 2

    def test_single_file(self, tmp_path: Path) -> None:
        """1 file produces 1 chunk regardless of worker count."""
        p = tmp_path / "solo.py"
        p.write_text("x = 1\n")

        chunks = _split_lpt([p], 3)
        assert len(chunks) == 1
        assert chunks[0] == [p]

    def test_assigns_largest_first(self, tmp_path: Path) -> None:
        """LPT assigns the largest file first, then balances remaining."""
        big = tmp_path / "big.py"
        big.write_text("x" * 10000)
        smalls = []
        for i in range(3):
            p = tmp_path / f"small{i}.py"
            p.write_text("x" * 10)
            smalls.append(p)

        chunks = _split_lpt([big, *smalls], 2)
        assert len(chunks) == 2
        # LPT assigns big first to one worker, then all smalls to the other
        # (since big >> 3*small, the other worker stays lighter throughout).
        chunk_files = [{f.name for f in c} for c in chunks]
        big_chunk = next(s for s in chunk_files if "big.py" in s)
        small_chunk = next(s for s in chunk_files if "big.py" not in s)
        assert big_chunk == {"big.py"}
        assert small_chunk == {"small0.py", "small1.py", "small2.py"}


# ---------------------------------------------------------------------------
# Worker count resolution
# ---------------------------------------------------------------------------


class TestResolveWorkers:
    """Unit tests for _resolve_workers."""

    def test_none_returns_1(self) -> None:
        assert _resolve_workers(10, None) == 1

    def test_one_returns_1(self) -> None:
        assert _resolve_workers(10, 1) == 1

    def test_capped_at_file_count(self) -> None:
        """Workers cannot exceed file count."""
        assert _resolve_workers(2, 8) == 2

    def test_explicit_workers(self) -> None:
        """Explicit workers used when less than file count and CPU count."""
        import os

        cpus = os.cpu_count() or 4
        result = _resolve_workers(100, 2)
        assert result == min(2, cpus)
