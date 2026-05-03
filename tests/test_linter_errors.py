"""Tests for linter error recovery.

The linter should gracefully handle all error conditions without crashing:
non-existent files, binary files, syntax errors, and rule exceptions.
"""

from __future__ import annotations

from pathlib import Path

from rude.core.linter import Linter
from rude.core.rule_discovery import discover_rules
from rude.core.types import Severity


def _make_linter(select: list[str]) -> Linter:
    """Build a Linter with the given rule selection."""
    linter = Linter()
    rules = discover_rules(select=select)
    linter.register_all(rules)
    return linter


# ---------------------------------------------------------------------------
# Non-existent file
# ---------------------------------------------------------------------------


class TestNonExistentFile:
    """check_file on a missing path must not crash."""

    def test_returns_e000(self) -> None:
        """A non-existent file produces an E000 diagnostic."""
        linter = _make_linter(select=["E711", "F401"])
        diags = list(linter.check_file("/tmp/does_not_exist_rude_test.py"))
        assert len(diags) == 1
        assert diags[0].code == "E000"
        assert diags[0].severity == Severity.ERROR
        assert "not found" in diags[0].message.lower()

    def test_streaming_handles_missing_file(self, tmp_path: Path) -> None:
        """Streaming path handles a missing file in the batch gracefully."""
        good = tmp_path / "ok.py"
        good.write_text("x = 1\n")
        missing = tmp_path / "gone.py"  # does not exist

        linter = _make_linter(select=["E711"])
        diags = list(linter.check_paths_parallel([str(good), str(missing)], already_resolved=True))

        # The missing file should produce an E000, the good file nothing
        codes = [d.code for _, d in diags]
        assert "E000" in codes


# ---------------------------------------------------------------------------
# Binary file
# ---------------------------------------------------------------------------


class TestBinaryFile:
    """check_file on a binary blob must not crash."""

    def test_does_not_crash(self, tmp_path: Path) -> None:
        """A binary file is processed without raising an exception."""
        f = tmp_path / "data.py"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        linter = _make_linter(select=["E711", "F401"])
        # Should not raise -- may produce diagnostics or an empty list
        diags = list(linter.check_file(str(f)))
        # No crash is the primary assertion; just verify types
        assert isinstance(diags, list)

    def test_streaming_does_not_crash(self, tmp_path: Path) -> None:
        """The streaming path handles binary files without crashing."""
        f = tmp_path / "data.py"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        linter = _make_linter(select=["E711"])
        diags = list(linter.check_paths_parallel([str(f)], already_resolved=True))
        assert isinstance(diags, list)


# ---------------------------------------------------------------------------
# Syntax errors
# ---------------------------------------------------------------------------


class TestSyntaxError:
    """Files with invalid Python should produce E999."""

    def test_unterminated_function(self, tmp_path: Path) -> None:
        """An unterminated function def produces E999."""
        f = tmp_path / "broken.py"
        f.write_text("def f(\n")
        linter = _make_linter(select=["E711"])
        diags = list(linter.check_file(str(f)))
        codes = [d.code for d in diags]
        assert "E999" in codes

    def test_invalid_syntax(self, tmp_path: Path) -> None:
        """Completely invalid syntax produces E999."""
        f = tmp_path / "bad.py"
        f.write_text("class :\n    pass\n")
        linter = _make_linter(select=["E711"])
        diags = list(linter.check_file(str(f)))
        codes = [d.code for d in diags]
        assert "E999" in codes

    def test_e999_is_error_severity(self, tmp_path: Path) -> None:
        """E999 diagnostics have ERROR severity."""
        f = tmp_path / "bad.py"
        f.write_text("def f(\n")
        linter = _make_linter(select=["E711"])
        diags = list(linter.check_file(str(f)))
        e999 = [d for d in diags if d.code == "E999"]
        assert len(e999) >= 1
        assert all(d.severity == Severity.ERROR for d in e999)

    def test_syntax_error_has_location(self, tmp_path: Path) -> None:
        """E999 diagnostics include a valid location."""
        f = tmp_path / "bad.py"
        f.write_text("x = 1\ndef f(\n")
        linter = _make_linter(select=["E711"])
        diags = list(linter.check_file(str(f)))
        e999 = [d for d in diags if d.code == "E999"]
        assert len(e999) >= 1
        # Location should be positive (1-indexed line)
        assert e999[0].location.line >= 1


# ---------------------------------------------------------------------------
# Empty file
# ---------------------------------------------------------------------------


class TestEmptyFile:
    """An empty file should produce no diagnostics and not crash."""

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("")
        linter = _make_linter(select=["E711", "F401"])
        diags = list(linter.check_file(str(f)))
        assert diags == []

    def test_empty_file_streaming(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("")
        linter = _make_linter(select=["E711", "F401"])
        diags = list(linter.check_paths_parallel([str(f)], already_resolved=True))
        assert diags == []


# ---------------------------------------------------------------------------
# Encoding edge cases
# ---------------------------------------------------------------------------


class TestEncodingEdgeCases:
    """Non-UTF-8 files should not crash the linter."""

    def test_latin1_file(self, tmp_path: Path) -> None:
        """A Latin-1 encoded file is handled without crashing."""
        f = tmp_path / "latin1.py"
        # Latin-1 bytes that are invalid UTF-8
        f.write_bytes(b"# -*- coding: latin-1 -*-\nx = '\xe9l\xe8ve'\n")
        linter = _make_linter(select=["E711"])
        # Should not raise
        diags = list(linter.check_file(str(f)))
        assert isinstance(diags, list)

    def test_null_bytes(self, tmp_path: Path) -> None:
        """A file containing null bytes does not crash."""
        f = tmp_path / "nulls.py"
        f.write_bytes(b"x = 1\n\x00\ny = 2\n")
        linter = _make_linter(select=["E711"])
        diags = list(linter.check_file(str(f)))
        assert isinstance(diags, list)


# ---------------------------------------------------------------------------
# Rule exception recovery
# ---------------------------------------------------------------------------


class TestRuleExceptionRecovery:
    """A rule that raises should produce E001, not crash the linter."""

    def test_check_source_with_broken_rule(self) -> None:
        """A rule raising during check() produces E001."""
        from collections.abc import Iterator
        from typing import ClassVar

        from rude.core.node_types import NodeType
        from rude.core.rule import Rule
        from rude.core.types import Diagnostic

        class BrokenRule(Rule):
            code: ClassVar[str] = "XTEST"
            message: ClassVar[str] = "broken"
            node_types = {NodeType.CALL}

            def check(self, node: object) -> Iterator[Diagnostic]:
                raise RuntimeError("intentional failure")

        linter = Linter()
        linter.register(BrokenRule())
        # Source has a call expression to trigger the rule
        diags = list(linter.check_source("print('hello')\n"))
        codes = [d.code for d in diags]
        assert "E001" in codes
        e001 = [d for d in diags if d.code == "E001"]
        assert "intentional failure" in e001[0].message

    def test_check_source_with_broken_line_rule(self) -> None:
        """A line rule raising during check_line() produces E001."""
        from collections.abc import Iterator
        from typing import ClassVar

        from rude.core.rule import LineRule
        from rude.core.types import Diagnostic, FileContext

        class BrokenLineRule(LineRule):
            code: ClassVar[str] = "XLTEST"
            message: ClassVar[str] = "broken line"

            def check_line(
                self,
                line: str,
                lineno: int,
                ctx: FileContext,
                *,
                comment_pos: int = -1,
            ) -> Iterator[Diagnostic]:
                raise RuntimeError("line rule failure")

        linter = Linter()
        linter.register(BrokenLineRule())
        diags = list(linter.check_source("x = 1\n"))
        codes = [d.code for d in diags]
        assert "E001" in codes
        e001 = [d for d in diags if d.code == "E001"]
        assert "line rule failure" in e001[0].message
