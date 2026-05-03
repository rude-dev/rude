"""Integration tests for the CLI entry point (python -m rude)."""

from __future__ import annotations

import json
import subprocess
import sys

PYTHON = sys.executable


def run_rude(*args: str) -> subprocess.CompletedProcess[str]:
    """Run `python -m rude` with the given arguments."""
    return subprocess.run(
        [PYTHON, "-m", "rude", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


# --- Exit codes ---


def test_clean_file_returns_zero(tmp_path):
    """A clean file with no violations should produce exit code 0."""
    f = tmp_path / "clean.py"
    f.write_text("x = 1\n")
    result = run_rude("check", "--select=E711", str(f))
    assert result.returncode == 0


def test_file_with_errors_returns_one(tmp_path):
    """A file triggering an ERROR-severity rule should produce exit code 1."""
    f = tmp_path / "bad.py"
    f.write_text("raise NotImplemented\n")
    result = run_rude("check", "--select=F901", str(f))
    assert result.returncode == 1
    assert "F901" in result.stdout


def test_file_with_errors_returns_nonzero(tmp_path):
    """Diagnostics default to ERROR severity and cause non-zero exit."""
    f = tmp_path / "warn.py"
    f.write_text("x = None\nif x == None:\n    pass\n")
    result = run_rude("check", "--select=E711", str(f))
    assert result.returncode == 1
    assert "E711" in result.stdout


# --- --select filtering ---


def test_select_limits_rules(tmp_path):
    """--select should restrict output to only the selected rule."""
    f = tmp_path / "multi.py"
    # Triggers both E711 (comparison to None) and F901 (raise NotImplemented)
    f.write_text("x = None\nif x == None:\n    pass\nraise NotImplemented\n")
    result = run_rude("check", "--select=F901", str(f))
    assert "F901" in result.stdout
    assert "E711" not in result.stdout


# --- --ignore filtering ---


def test_ignore_suppresses_rule(tmp_path):
    """--ignore should prevent the ignored rule from appearing."""
    f = tmp_path / "ignore.py"
    f.write_text("x = None\nif x == None:\n    pass\nraise NotImplemented\n")
    result = run_rude("check", "--select=E711,F901", "--ignore=F901", str(f))
    assert "E711" in result.stdout
    assert "F901" not in result.stdout
    # E711 is now ERROR (default severity), so exit 1
    assert result.returncode == 1


# --- --format json ---


def test_json_format_produces_valid_json(tmp_path):
    """--format json should emit one valid JSON object per diagnostic."""
    f = tmp_path / "js.py"
    f.write_text("raise NotImplemented\n")
    result = run_rude("check", "--select=F901", "--format=json", str(f))
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) >= 1
    obj = json.loads(lines[0])
    assert obj["code"] == "F901"
    assert obj["severity"] == "error"
    assert "line" in obj
    assert "column" in obj
    assert "file" in obj
    assert "message" in obj
    assert "fixable" in obj


def test_json_format_clean_file_no_output(tmp_path):
    """--format json on a clean file should produce no JSON lines."""
    f = tmp_path / "clean.py"
    f.write_text("x = 1\n")
    result = run_rude("check", "--select=E711", "--format=json", str(f))
    assert result.returncode == 0
    # No diagnostics -> no JSON output (no summary either in json mode)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 0


# --- --fix ---


def test_fix_modifies_file(tmp_path):
    """--fix should rewrite the file with the applied fix."""
    f = tmp_path / "fixme.py"
    f.write_text("x = None\nif x == None:\n    pass\n")
    result = run_rude("check", "--select=E711", "--fix", str(f))
    assert result.returncode == 0
    fixed = f.read_text()
    assert "x is None" in fixed
    assert "x == None" not in fixed


# --- Non-existent path ---


def test_nonexistent_path_returns_error():
    """A non-existent path should produce exit code 1."""
    result = run_rude("check", "--select=E711", "/nonexistent/path.py")
    assert result.returncode == 1


# --- --version ---


def test_version_flag():
    """--version should print the version and exit 0."""
    result = run_rude("--version")
    assert result.returncode == 0
    assert "rude" in result.stdout
    # Version string should contain a version-like pattern
    assert "0." in result.stdout or "1." in result.stdout


# --- No arguments ---


def test_no_arguments_defaults_to_check():
    """Running with no arguments should default to 'rude check .'."""
    result = run_rude()
    # Should run check on cwd, not show help
    assert result.returncode in (0, 1)
    assert "usage:" not in result.stdout.lower()


# --- --max-line-length ---


def test_max_line_length_override(tmp_path):
    """--max-line-length should override the default 79-char limit."""
    f = tmp_path / "long.py"
    # 85-char line: triggers E501 with default 79 but not with 100
    f.write_text("x = " + '"a' * 42 + '"\n')
    # With default limit (79), E501 should fire
    result_default = run_rude("check", "--select=E501", str(f))
    assert "E501" in result_default.stdout

    # With raised limit, E501 should not fire
    result_raised = run_rude("check", "--select=E501", "--max-line-length=100", str(f))
    assert "E501" not in result_raised.stdout


# --- --max-errors ---


def test_max_errors_stops_after_n_in_default_mode(tmp_path):
    """--max-errors must stop after N errors in the default --jobs=1 path."""
    f = tmp_path / "many.py"
    f.write_text(
        "x = None\nif x == None:\n    pass\ny = None\nif y == None:\n    pass\nz = None\nif z == None:\n    pass\n"
    )
    result = run_rude("check", "--select=E711", "--max-errors=1", "--format=compact", str(f))
    assert result.returncode == 1
    e711_lines = [line for line in result.stdout.splitlines() if "E711" in line]
    assert len(e711_lines) == 1, f"Expected 1 E711 diagnostic, got {len(e711_lines)}: {e711_lines}"


# --- list subcommand ---


def test_list_subcommand():
    """The 'list' subcommand should list available rules and exit 0."""
    result = run_rude("list")
    assert result.returncode == 0
    # Should contain at least some well-known rule codes
    assert "E711" in result.stdout
    assert "E501" in result.stdout


# --- Compact format ---


def test_compact_format(tmp_path):
    """--format compact should emit path:line:col: CODE message."""
    f = tmp_path / "comp.py"
    f.write_text("raise NotImplemented\n")
    result = run_rude("check", "--select=F901", "--format=compact", str(f))
    assert result.returncode == 1
    line = result.stdout.strip()
    parts = line.split(":")
    # path:line:col: CODE message
    assert len(parts) >= 4
    assert "F901" in line


# --- lint alias ---


def test_lint_is_alias_of_check(tmp_path):
    """Running `rude lint` must behave identically to `rude check`."""
    f = tmp_path / "bad.py"
    f.write_text("raise NotImplemented\n")
    result_check = run_rude("check", "--select=F901", str(f))
    result_lint = run_rude("lint", "--select=F901", str(f))
    assert result_check.returncode == result_lint.returncode
    assert result_check.stdout == result_lint.stdout
    assert result_check.stderr == result_lint.stderr


# --- parallelism ---


def test_jobs_produces_same_output_as_single_process(tmp_path):
    """`rude check --jobs=4` must produce identical diagnostics to --jobs=1.

    Regression guard against the fragile-worker-state bug where multiprocessing
    workers could silently lose rule config. The test creates a small fixture
    tree with one file that violates F901 and one that violates E711 and
    verifies the set of diagnostics is the same under both job counts.
    """
    for name, body in {
        "a.py": "x = None\nif x == None:\n    pass\n",  # E711
        "b.py": "raise NotImplemented\n",  # F901
    }.items():
        (tmp_path / name).write_text(body)

    r1 = run_rude("check", "--select=E711,F901", "--format=compact", str(tmp_path))
    r4 = run_rude("check", "--jobs=4", "--select=E711,F901", "--format=compact", str(tmp_path))

    # Normalise line order (parallel runs may emit in different orders)
    def normalise(s: str) -> list[str]:
        return sorted(line for line in s.splitlines() if line.strip())

    assert r1.returncode == r4.returncode
    assert normalise(r1.stdout) == normalise(r4.stdout)
