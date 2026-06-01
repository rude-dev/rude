"""Tests for file discovery with gitignore support."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest

from rude.core.file_finder import ALWAYS_SKIP, _GitIgnore, find_python_files, resolve_paths


class TestAlwaysSkip:
    """Tests for the ALWAYS_SKIP constant."""

    def test_is_frozenset(self) -> None:
        """ALWAYS_SKIP is a frozenset."""
        assert isinstance(ALWAYS_SKIP, frozenset)

    def test_contains_common_dirs(self) -> None:
        """ALWAYS_SKIP contains well-known directories to skip."""
        expected = {
            ".git",
            ".hg",
            "__pycache__",
            ".venv",
            "venv",
            "node_modules",
            ".tox",
            ".nox",
            ".mypy_cache",
            ".pytest_cache",
            "dist",
            "build",
        }
        assert expected.issubset(ALWAYS_SKIP)

    def test_contains_glob_patterns(self) -> None:
        """ALWAYS_SKIP includes glob patterns like *.egg-info."""
        assert "*.egg-info" in ALWAYS_SKIP


class TestFindPythonFiles:
    """Tests for find_python_files()."""

    def test_finds_py_files(self, tmp_path: Path) -> None:
        """Discovers .py files in a directory."""
        (tmp_path / "hello.py").write_text("pass")
        (tmp_path / "world.py").write_text("pass")

        result = list(find_python_files(tmp_path))

        assert len(result) == 2
        names = [p.name for p in result]
        assert "hello.py" in names
        assert "world.py" in names

    def test_ignores_non_py_files(self, tmp_path: Path) -> None:
        """Non-.py files are not returned."""
        (tmp_path / "script.py").write_text("pass")
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "data.json").write_text("{}")
        (tmp_path / "Makefile").write_text("all:")

        result = list(find_python_files(tmp_path))

        assert len(result) == 1
        assert result[0].name == "script.py"

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Returns nothing for an empty directory."""
        result = list(find_python_files(tmp_path))
        assert result == []

    def test_sorted_output_files(self, tmp_path: Path) -> None:
        """Files within a directory are sorted by name."""
        for name in ["zebra.py", "alpha.py", "middle.py"]:
            (tmp_path / name).write_text("pass")

        result = list(find_python_files(tmp_path))
        names = [p.name for p in result]

        assert names == ["alpha.py", "middle.py", "zebra.py"]

    def test_sorted_output_dirs(self, tmp_path: Path) -> None:
        """Directories are traversed in sorted order."""
        for dirname in ["zoo", "apple", "mango"]:
            d = tmp_path / dirname
            d.mkdir()
            (d / "mod.py").write_text("pass")

        result = list(find_python_files(tmp_path))
        parents = [p.parent.name for p in result]

        assert parents == ["apple", "mango", "zoo"]

    def test_recursive_discovery(self, tmp_path: Path) -> None:
        """Recursively finds .py files in nested directories."""
        (tmp_path / "top.py").write_text("pass")
        sub = tmp_path / "pkg"
        sub.mkdir()
        (sub / "inner.py").write_text("pass")
        deep = sub / "sub"
        deep.mkdir()
        (deep / "deep.py").write_text("pass")

        result = list(find_python_files(tmp_path))
        names = [p.name for p in result]

        assert "top.py" in names
        assert "inner.py" in names
        assert "deep.py" in names
        assert len(result) == 3

    def test_files_before_subdirs(self, tmp_path: Path) -> None:
        """Files in a directory are yielded before descending into subdirs."""
        (tmp_path / "aaa.py").write_text("pass")
        sub = tmp_path / "bbb_dir"
        sub.mkdir()
        (sub / "child.py").write_text("pass")

        result = list(find_python_files(tmp_path))

        assert result[0].name == "aaa.py"
        assert result[1].name == "child.py"

    def test_skips_always_skip_dirs(self, tmp_path: Path) -> None:
        """Directories in ALWAYS_SKIP are not traversed."""
        (tmp_path / "good.py").write_text("pass")
        for skip_dir in ["__pycache__", ".venv", "node_modules", "build", "dist"]:
            d = tmp_path / skip_dir
            d.mkdir()
            (d / "hidden.py").write_text("pass")

        result = list(find_python_files(tmp_path))

        assert len(result) == 1
        assert result[0].name == "good.py"

    def test_skips_egg_info_dirs(self, tmp_path: Path) -> None:
        """Directories matching *.egg-info glob pattern are skipped."""
        (tmp_path / "good.py").write_text("pass")
        egg = tmp_path / "mypackage.egg-info"
        egg.mkdir()
        (egg / "hidden.py").write_text("pass")

        result = list(find_python_files(tmp_path))

        assert len(result) == 1
        assert result[0].name == "good.py"

    def test_skips_hidden_directories(self, tmp_path: Path) -> None:
        """Directories starting with '.' are skipped."""
        (tmp_path / "visible.py").write_text("pass")
        for hidden in [".hidden", ".secret", ".config"]:
            d = tmp_path / hidden
            d.mkdir()
            (d / "internal.py").write_text("pass")

        result = list(find_python_files(tmp_path))

        assert len(result) == 1
        assert result[0].name == "visible.py"

    def test_skips_dot_git(self, tmp_path: Path) -> None:
        """.git directory is skipped (both hidden-dir and ALWAYS_SKIP)."""
        (tmp_path / "app.py").write_text("pass")
        git = tmp_path / ".git"
        git.mkdir()
        (git / "hooks.py").write_text("pass")

        result = list(find_python_files(tmp_path))

        assert len(result) == 1
        assert result[0].name == "app.py"

    def test_symlink_dirs_not_followed(self, tmp_path: Path) -> None:
        """Symlinked directories are not followed (follow_symlinks=False)."""
        real = tmp_path / "real"
        real.mkdir()
        (real / "mod.py").write_text("pass")

        link = tmp_path / "linked"
        link.symlink_to(real)

        # The symlink target is a directory, but is_dir(follow_symlinks=False)
        # returns False for a symlink, so it will be treated as a file.
        # Since it does not end with .py, it will be skipped.
        result = list(find_python_files(tmp_path))
        parents = [p.parent.name for p in result]

        assert "real" in parents
        assert "linked" not in parents

    def test_accepts_string_root(self, tmp_path: Path) -> None:
        """root can be a string, not just a Path."""
        (tmp_path / "mod.py").write_text("pass")

        result = list(find_python_files(str(tmp_path)))

        assert len(result) == 1
        assert result[0].name == "mod.py"

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix permissions")
    def test_permission_error_gracefully_skipped(self, tmp_path: Path) -> None:
        """Directories with no read permission are silently skipped."""
        (tmp_path / "good.py").write_text("pass")
        forbidden = tmp_path / "forbidden"
        forbidden.mkdir()
        (forbidden / "secret.py").write_text("pass")
        forbidden.chmod(0o000)

        try:
            result = list(find_python_files(tmp_path))
            names = [p.name for p in result]
            assert "good.py" in names
            assert "secret.py" not in names
        finally:
            forbidden.chmod(stat.S_IRWXU)

    def test_returns_resolved_paths(self, tmp_path: Path) -> None:
        """Returned paths are absolute and resolved."""
        (tmp_path / "mod.py").write_text("pass")

        result = list(find_python_files(tmp_path))

        assert result[0].is_absolute()
        assert str(result[0]) == str(result[0].resolve())


class TestFindPythonFilesGitignore:
    """Tests for gitignore integration in find_python_files()."""

    def test_respects_gitignore_file_pattern(self, tmp_path: Path) -> None:
        """Files matching .gitignore patterns are excluded."""
        (tmp_path / ".gitignore").write_text("ignored.py\n")
        (tmp_path / "kept.py").write_text("pass")
        (tmp_path / "ignored.py").write_text("pass")

        result = list(find_python_files(tmp_path))
        names = [p.name for p in result]

        assert "kept.py" in names
        assert "ignored.py" not in names

    def test_respects_gitignore_wildcard(self, tmp_path: Path) -> None:
        """Wildcard patterns in .gitignore work."""
        (tmp_path / ".gitignore").write_text("test_*.py\n")
        (tmp_path / "app.py").write_text("pass")
        (tmp_path / "test_app.py").write_text("pass")
        (tmp_path / "test_utils.py").write_text("pass")

        result = list(find_python_files(tmp_path))
        names = [p.name for p in result]

        assert names == ["app.py"]

    def test_respects_gitignore_dir_pattern(self, tmp_path: Path) -> None:
        """Directory patterns (trailing slash) in .gitignore work."""
        (tmp_path / ".gitignore").write_text("generated/\n")
        (tmp_path / "app.py").write_text("pass")
        gen = tmp_path / "generated"
        gen.mkdir()
        (gen / "auto.py").write_text("pass")

        result = list(find_python_files(tmp_path))
        names = [p.name for p in result]

        assert "app.py" in names
        assert "auto.py" not in names

    def test_gitignore_disabled(self, tmp_path: Path) -> None:
        """respect_gitignore=False ignores the .gitignore file."""
        (tmp_path / ".gitignore").write_text("ignored.py\n")
        (tmp_path / "kept.py").write_text("pass")
        (tmp_path / "ignored.py").write_text("pass")

        result = list(find_python_files(tmp_path, respect_gitignore=False))
        names = [p.name for p in result]

        assert "kept.py" in names
        assert "ignored.py" in names

    def test_no_gitignore_file(self, tmp_path: Path) -> None:
        """Works fine when no .gitignore exists."""
        (tmp_path / "mod.py").write_text("pass")

        result = list(find_python_files(tmp_path))

        assert len(result) == 1
        assert result[0].name == "mod.py"

    def test_gitignore_comments_and_blanks(self, tmp_path: Path) -> None:
        """Comments and blank lines in .gitignore are ignored."""
        (tmp_path / ".gitignore").write_text("# comment\n\nskipped.py\n\n# another\n")
        (tmp_path / "kept.py").write_text("pass")
        (tmp_path / "skipped.py").write_text("pass")

        result = list(find_python_files(tmp_path))
        names = [p.name for p in result]

        assert "kept.py" in names
        assert "skipped.py" not in names

    def test_respects_nested_gitignore(self, tmp_path: Path) -> None:
        """A .gitignore in a subdirectory excludes files within that subdirectory."""
        (tmp_path / "keep.py").write_text("pass")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / ".gitignore").write_text("ignored.py\n")
        (sub / "ignored.py").write_text("pass")
        (sub / "keep2.py").write_text("pass")

        result = list(find_python_files(tmp_path))
        names = {p.name for p in result}

        assert names == {"keep.py", "keep2.py"}


class TestGitIgnore:
    """Tests for the _GitIgnore pattern matcher."""

    def test_simple_filename_match(self, tmp_path: Path) -> None:
        """Matches exact filenames."""
        gi = _GitIgnore(["secret.py"], tmp_path)

        assert gi.match("secret.py") is True
        assert gi.match("other.py") is False

    def test_wildcard_match(self, tmp_path: Path) -> None:
        """Matches wildcard patterns."""
        gi = _GitIgnore(["*.pyc"], tmp_path)

        assert gi.match("module.pyc") is True
        assert gi.match("module.py") is False

    def test_directory_only_pattern(self, tmp_path: Path) -> None:
        """Patterns with trailing slash only match directories."""
        gi = _GitIgnore(["logs/"], tmp_path)

        assert gi.match("logs/") is True
        assert gi.match("logs") is False  # not marked as dir

    def test_negation_pattern(self, tmp_path: Path) -> None:
        """Negation patterns (!) un-ignore previously matched paths."""
        gi = _GitIgnore(["*.py", "!important.py"], tmp_path)

        assert gi.match("garbage.py") is True
        assert gi.match("important.py") is False

    def test_negation_only_applies_when_matched(self, tmp_path: Path) -> None:
        """Negation has no effect if the path was not matched by positive patterns."""
        gi = _GitIgnore(["*.txt", "!keep.py"], tmp_path)

        # keep.py is not matched by *.txt, so negation does not apply
        assert gi.match("keep.py") is False
        assert gi.match("notes.txt") is True

    def test_comments_ignored(self, tmp_path: Path) -> None:
        """Lines starting with # are comments."""
        gi = _GitIgnore(["# this is a comment", "ignored.py"], tmp_path)

        assert gi.match("# this is a comment") is False
        assert gi.match("ignored.py") is True

    def test_blank_lines_ignored(self, tmp_path: Path) -> None:
        """Blank and whitespace-only lines are skipped."""
        gi = _GitIgnore(["", "  ", "ignored.py"], tmp_path)

        assert gi.match("ignored.py") is True

    def test_path_with_slash_pattern(self, tmp_path: Path) -> None:
        """Patterns containing / match against the full relative path."""
        gi = _GitIgnore(["src/generated.py"], tmp_path)

        assert gi.match("src/generated.py") is True
        assert gi.match("generated.py") is False

    def test_leading_slash_treated_as_path_pattern(self, tmp_path: Path) -> None:
        """Leading / is stripped, making the pattern path-based (contains /)."""
        gi = _GitIgnore(["/root_only.py"], tmp_path)

        assert gi.match("root_only.py") is True
        # The leading / is stripped, so this is matched as a path pattern
        # with fnmatch against **/root_only.py
        assert gi.match("sub/root_only.py") is True

    def test_no_slash_matches_any_component(self, tmp_path: Path) -> None:
        """Patterns without / match against any path component."""
        gi = _GitIgnore(["secret.py"], tmp_path)

        assert gi.match("secret.py") is True
        assert gi.match("pkg/secret.py") is True
        assert gi.match("pkg/sub/secret.py") is True

    def test_directory_pattern_does_not_match_file(self, tmp_path: Path) -> None:
        """A directory-only pattern does not match a file path."""
        gi = _GitIgnore(["output/"], tmp_path)

        assert gi.match("output/") is True
        assert gi.match("output/file.py") is False

    def test_wildcard_in_directory_name(self, tmp_path: Path) -> None:
        """Wildcard pattern matching directory components."""
        gi = _GitIgnore(["test_*"], tmp_path)

        assert gi.match("test_foo.py") is True
        assert gi.match("pkg/test_bar.py") is True

    def test_multiple_positive_patterns(self, tmp_path: Path) -> None:
        """Multiple positive patterns are OR-ed together."""
        gi = _GitIgnore(["*.pyc", "*.pyo"], tmp_path)

        assert gi.match("mod.pyc") is True
        assert gi.match("mod.pyo") is True
        assert gi.match("mod.py") is False

    def test_empty_patterns_list(self, tmp_path: Path) -> None:
        """An empty pattern list matches nothing."""
        gi = _GitIgnore([], tmp_path)

        assert gi.match("anything.py") is False

    def test_strip_whitespace(self, tmp_path: Path) -> None:
        """Leading and trailing whitespace is stripped from patterns."""
        gi = _GitIgnore(["  ignored.py  "], tmp_path)

        assert gi.match("ignored.py") is True


class TestResolvePaths:
    """Tests for resolve_paths()."""

    def test_file_path(self, tmp_path: Path) -> None:
        """A .py file path is yielded directly."""
        f = tmp_path / "script.py"
        f.write_text("pass")

        result = list(resolve_paths([f]))

        assert len(result) == 1
        assert result[0] == f

    def test_directory_path(self, tmp_path: Path) -> None:
        """A directory path triggers recursive Python file discovery."""
        (tmp_path / "a.py").write_text("pass")
        (tmp_path / "b.py").write_text("pass")

        result = list(resolve_paths([tmp_path]))
        names = [p.name for p in result]

        assert "a.py" in names
        assert "b.py" in names

    def test_non_existent_path_skipped(self, tmp_path: Path) -> None:
        """Non-existent paths are silently skipped."""
        missing = tmp_path / "does_not_exist.py"

        result = list(resolve_paths([missing]))

        assert result == []

    def test_non_py_file_skipped(self, tmp_path: Path) -> None:
        """Non-.py files are skipped even if they exist."""
        f = tmp_path / "data.txt"
        f.write_text("hello")

        result = list(resolve_paths([f]))

        assert result == []

    def test_mixed_inputs(self, tmp_path: Path) -> None:
        """Handles a mix of files, directories, and missing paths."""
        py_file = tmp_path / "direct.py"
        py_file.write_text("pass")
        sub = tmp_path / "pkg"
        sub.mkdir()
        (sub / "inner.py").write_text("pass")
        missing = tmp_path / "gone.py"
        txt = tmp_path / "notes.txt"
        txt.write_text("hello")

        result = list(resolve_paths([py_file, sub, missing, txt]))
        names = [p.name for p in result]

        assert "direct.py" in names
        assert "inner.py" in names
        assert "gone.py" not in names
        assert "notes.txt" not in names

    def test_accepts_string_paths(self, tmp_path: Path) -> None:
        """String paths are accepted alongside Path objects."""
        f = tmp_path / "mod.py"
        f.write_text("pass")

        result = list(resolve_paths([str(f)]))

        assert len(result) == 1

    def test_empty_input(self) -> None:
        """Empty input yields no results."""
        result = list(resolve_paths([]))
        assert result == []

    def test_directory_applies_always_skip(self, tmp_path: Path) -> None:
        """Directories resolved via resolve_paths still skip ALWAYS_SKIP dirs."""
        (tmp_path / "good.py").write_text("pass")
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.py").write_text("pass")

        result = list(resolve_paths([tmp_path]))
        names = [p.name for p in result]

        assert "good.py" in names
        assert "cached.py" not in names
