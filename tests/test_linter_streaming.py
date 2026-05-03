"""Tests for the streaming batch path (_check_files_streaming).

The streaming path is the DEFAULT production path when --jobs=1.
It uses Rust's batch_analyze_iter for parallel file processing.
"""

from __future__ import annotations

from pathlib import Path

from rude.core.linter import CheckOptions, Linter
from rude.core.rule_discovery import discover_rules
from rude.core.types import Diagnostic


def _make_linter(select: list[str]) -> Linter:
    """Build a Linter with the given rule selection."""
    linter = Linter()
    rules = discover_rules(select=select)
    linter.register_all(rules)
    return linter


def _write_files(tmp_path: Path) -> dict[str, Path]:
    """Create a set of test files with known diagnostics.

    Returns a mapping of logical name -> path.
    """
    files = {}

    # Clean file -- no diagnostics expected
    p = tmp_path / "clean.py"
    p.write_text("x = 1\ny = x + 2\n")
    files["clean"] = p

    # F401: unused import
    p = tmp_path / "unused_import.py"
    p.write_text("import os\n\n\ndef f():\n    pass\n")
    files["unused_import"] = p

    # E711: comparison to None
    p = tmp_path / "comparison.py"
    p.write_text("x = None\nif x == None:\n    pass\n")
    files["comparison"] = p

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


class TestStreamingMatchesSingleFile:
    """Streaming batch results must match single-file check results."""

    def test_diagnostic_codes_match(self, tmp_path: Path) -> None:
        """Streaming and single-file paths produce identical diagnostic codes."""
        files = _write_files(tmp_path)
        linter = _make_linter(select=["E711", "F401", "E401"])
        paths = [str(p) for p in files.values()]

        # Streaming path (default for workers=None)
        streaming_diags = list(linter.check_paths_parallel(paths, already_resolved=True))

        # Single-file path
        single_diags = []
        for p in paths:
            for d in linter.check_file(p):
                single_diags.append((Path(p), d))

        streaming_codes = sorted(d.code for _, d in streaming_diags)
        single_codes = sorted(d.code for _, d in single_diags)
        assert streaming_codes == single_codes

    def test_diagnostic_locations_match(self, tmp_path: Path) -> None:
        """Streaming and single-file paths produce identical locations."""
        files = _write_files(tmp_path)
        linter = _make_linter(select=["E711", "F401"])
        paths = [str(p) for p in files.values()]

        streaming_diags = list(linter.check_paths_parallel(paths, already_resolved=True))
        single_diags = []
        for p in paths:
            for d in linter.check_file(p):
                single_diags.append((Path(p), d))

        def key(item: tuple[Path, Diagnostic]) -> tuple[str, str, int, int]:
            path, d = item
            return (str(path), d.code, d.location.line, d.location.column)

        assert sorted(streaming_diags, key=key) == sorted(single_diags, key=key)


class TestStreamingProcessesAllFiles:
    """Every file must be processed -- no silent drops."""

    def test_all_files_appear_in_results(self, tmp_path: Path) -> None:
        """Each file with violations appears at least once in output."""
        files = _write_files(tmp_path)
        linter = _make_linter(select=["E711", "F401", "E401"])
        paths = [str(p) for p in files.values()]

        streaming_diags = list(linter.check_paths_parallel(paths, already_resolved=True))

        files_with_diags = {str(p) for p, _ in streaming_diags}
        # These files definitely have violations
        assert str(files["unused_import"]) in files_with_diags
        assert str(files["comparison"]) in files_with_diags
        assert str(files["multi_import"]) in files_with_diags
        assert str(files["mixed"]) in files_with_diags

    def test_clean_files_produce_no_diags(self, tmp_path: Path) -> None:
        """Clean files should not appear in diagnostic output."""
        files = _write_files(tmp_path)
        linter = _make_linter(select=["E711", "F401", "E401"])
        paths = [str(p) for p in files.values()]

        streaming_diags = list(linter.check_paths_parallel(paths, already_resolved=True))

        files_with_diags = {str(p) for p, _ in streaming_diags}
        assert str(files["clean"]) not in files_with_diags
        assert str(files["clean2"]) not in files_with_diags


class TestStreamingDiagnosticCounts:
    """Verify expected diagnostic counts from the streaming path."""

    def test_expected_counts(self, tmp_path: Path) -> None:
        """Each file produces the expected number of diagnostics."""
        files = _write_files(tmp_path)
        linter = _make_linter(select=["E711", "F401", "E401"])
        paths = [str(p) for p in files.values()]

        streaming_diags = list(linter.check_paths_parallel(paths, already_resolved=True))

        by_file: dict[str, list[str]] = {}
        for p, d in streaming_diags:
            by_file.setdefault(str(p), []).append(d.code)

        # unused_import.py: F401 (import os unused)
        assert by_file.get(str(files["unused_import"])) == ["F401"]
        # comparison.py: E711
        assert by_file.get(str(files["comparison"])) == ["E711"]
        # multi_import.py: E401
        assert by_file.get(str(files["multi_import"])) == ["E401"]
        # mixed.py: F401 (import json) + E711 (== None)
        mixed_codes = sorted(by_file.get(str(files["mixed"]), []))
        assert mixed_codes == ["E711", "F401"]

    def test_empty_file_list(self) -> None:
        """Passing an empty file list produces no diagnostics."""
        linter = _make_linter(select=["E711", "F401"])
        result = list(linter.check_paths_parallel([], already_resolved=True))
        assert result == []

    def test_single_clean_file(self, tmp_path: Path) -> None:
        """A single clean file produces no diagnostics."""
        f = tmp_path / "ok.py"
        f.write_text("x = 1\n")
        linter = _make_linter(select=["E711", "F401"])
        result = list(linter.check_paths_parallel([str(f)], already_resolved=True))
        assert result == []


class TestStreamingWithSyntaxErrors:
    """Streaming path handles syntax errors via E999."""

    def test_syntax_error_produces_e999(self, tmp_path: Path) -> None:
        """A file with invalid syntax should produce an E999 diagnostic."""
        f = tmp_path / "broken.py"
        f.write_text("def f(\n")
        linter = _make_linter(select=["E711", "F401"])
        diags = list(linter.check_paths_parallel([str(f)], already_resolved=True))
        codes = [d.code for _, d in diags]
        assert "E999" in codes

    def test_syntax_error_alongside_clean(self, tmp_path: Path) -> None:
        """A broken file does not prevent clean files from being processed."""
        broken = tmp_path / "broken.py"
        broken.write_text("def f(\n")
        clean = tmp_path / "clean.py"
        clean.write_text("x = 1\n")
        bad = tmp_path / "bad.py"
        bad.write_text("x = None\nif x == None:\n    pass\n")

        linter = _make_linter(select=["E711"])
        paths = [str(broken), str(clean), str(bad)]
        diags = list(linter.check_paths_parallel(paths, already_resolved=True))

        codes = {d.code for _, d in diags}
        # E999 from the broken file, E711 from the bad file
        assert "E999" in codes
        assert "E711" in codes


class TestStreamingOptions:
    """Verify CheckOptions are respected by the streaming path."""

    def test_default_options(self, tmp_path: Path) -> None:
        """Default options (workers=None) use the streaming path."""
        f = tmp_path / "bad.py"
        f.write_text("import os\n\n\ndef f():\n    pass\n")
        linter = _make_linter(select=["F401"])
        # workers=None -> streaming path
        opts = CheckOptions(workers=None)
        diags = list(linter.check_paths_parallel([str(f)], options=opts, already_resolved=True))
        assert len(diags) == 1
        assert diags[0][1].code == "F401"

    def test_workers_one_uses_streaming(self, tmp_path: Path) -> None:
        """workers=1 explicitly selects the streaming path."""
        f = tmp_path / "bad.py"
        f.write_text("import os\n\n\ndef f():\n    pass\n")
        linter = _make_linter(select=["F401"])
        opts = CheckOptions(workers=1)
        diags = list(linter.check_paths_parallel([str(f)], options=opts, already_resolved=True))
        assert len(diags) == 1
        assert diags[0][1].code == "F401"
