from pathlib import Path

import pytest

from rude.core.config import Config, find_config_file, load_config


def test_resolve_path_within_project(tmp_path: Path) -> None:
    config = Config(config_path=tmp_path / "pyproject.toml")
    result = config.resolve_path("tools/rules.py")
    assert result == (tmp_path / "tools" / "rules.py").resolve()


def test_resolve_path_rejects_traversal(tmp_path: Path) -> None:
    config = Config(config_path=tmp_path / "pyproject.toml")
    with pytest.raises(ValueError, match="outside project root"):
        config.resolve_path("../../../etc/evil.py")


def test_resolve_path_rejects_absolute(tmp_path: Path) -> None:
    config = Config(config_path=tmp_path / "pyproject.toml")
    with pytest.raises(ValueError, match="outside project root"):
        config.resolve_path("/etc/evil.py")


def test_resolve_path_no_config_rejects_outside_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When config_path is None, paths outside cwd are rejected."""
    monkeypatch.chdir(tmp_path)
    cfg = Config()  # no config_path
    with pytest.raises(ValueError, match="resolves outside cwd"):
        cfg.resolve_path("/etc/passwd")


def test_load_from_file_warns_on_invalid_toml(tmp_path: Path) -> None:
    """Malformed TOML emits a warning instead of silently returning defaults."""
    bad = tmp_path / "pyproject.toml"
    bad.write_text("[invalid toml\n")
    with pytest.warns(UserWarning, match="Failed to parse"):
        cfg = load_config(bad)
    assert cfg.select == []  # fallback to defaults


def test_valid_toml_round_trip(tmp_path: Path) -> None:
    """Write a pyproject.toml with [tool.rude] and verify it loads correctly."""
    toml = tmp_path / "pyproject.toml"
    toml.write_text('[tool.rude]\nselect = ["E711"]\n')
    cfg = load_config(toml)
    assert cfg.select == ["E711"]


def test_missing_tool_rude_section_returns_defaults(tmp_path: Path) -> None:
    """A pyproject.toml with no [tool.rude] returns default Config."""
    toml = tmp_path / "pyproject.toml"
    toml.write_text('[project]\nname = "foo"\n')
    cfg = load_config(toml)
    assert cfg.select == []
    assert cfg.ignore == []
    assert cfg.local_rules == []
    assert cfg.rule_options == {}


def test_config_field_extraction(tmp_path: Path) -> None:
    """All Config fields are populated from [tool.rude]."""
    toml = tmp_path / "pyproject.toml"
    toml.write_text(
        "[tool.rude]\n"
        'select = ["E7"]\n'
        'ignore = ["E711"]\n'
        'local-rules = ["tools/rules.py"]\n'
        "\n"
        "[tool.rude.rules.E501]\n"
        "max-line-length = 120\n"
    )
    cfg = load_config(toml)
    assert cfg.select == ["E7"]
    assert cfg.ignore == ["E711"]
    assert cfg.local_rules == ["tools/rules.py"]
    assert cfg.rule_options == {"E501": {"max-line-length": 120}}


def test_find_config_file_traversal(tmp_path: Path) -> None:
    """find_config_file walks up directories to locate [tool.rude]."""
    toml = tmp_path / "pyproject.toml"
    toml.write_text('[tool.rude]\nselect = ["E"]\n')
    child = tmp_path / "src" / "pkg"
    child.mkdir(parents=True)
    found = find_config_file(start=child)
    assert found == toml
