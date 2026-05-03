"""Configuration from pyproject.toml."""

from __future__ import annotations

import tomllib
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Config:
    """Rude configuration from [tool.rude]."""

    select: list[str] = field(default_factory=list)
    ignore: list[str] = field(default_factory=list)
    plugins: list[str] = field(default_factory=list)
    local_rules: list[str] = field(default_factory=list)
    rule_options: dict[str, dict[str, Any]] = field(default_factory=dict)
    config_path: Path | None = None

    def get_rule_options(self, code: str) -> dict[str, Any]:
        return self.rule_options.get(code, {})

    def resolve_path(self, path: str) -> Path:
        """Resolve a local-rules path relative to the config file.

        Raises ValueError if the resolved path escapes the project root.
        """
        p = Path(path)
        if not self.config_path:
            resolved = p.resolve()
            cwd = Path.cwd().resolve()
            if not resolved.is_relative_to(cwd):
                raise ValueError(f"local-rules path {path!r} resolves outside cwd ({cwd})")
            return resolved
        project_root = self.config_path.parent.resolve()
        resolved = p.resolve() if p.is_absolute() else (project_root / p).resolve()
        if not resolved.is_relative_to(project_root):
            raise ValueError(
                f"local-rules path {path!r} resolves outside project root ({project_root})"
            )
        return resolved


def load_config(path: Path | str | None = None) -> Config:
    """Load config from pyproject.toml."""
    config_path: Path | None
    if path:
        config_path = Path(path)
        if config_path.is_dir():
            config_path = config_path / "pyproject.toml"
    else:
        config_path = find_config_file()

    if not config_path or not config_path.exists():
        return Config()
    return _load_from_file(config_path)


def find_config_file(start: Path | None = None) -> Path | None:
    """Find pyproject.toml with [tool.rude] section."""
    current = (start or Path.cwd()).resolve()
    while True:
        cfg = current / "pyproject.toml"
        if cfg.exists():
            try:
                with open(cfg, "rb") as f:
                    data = tomllib.load(f)
                if "tool" in data and "rude" in data["tool"]:
                    return cfg
            except OSError:
                pass
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _load_from_file(path: Path) -> Config:
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as e:
        warnings.warn(f"Failed to parse {path}: {e}", UserWarning, stacklevel=2)
        return Config()

    rude = data.get("tool", {}).get("rude", {})
    if not rude:
        return Config()

    rules = rude.pop("rules", {})

    def get_list(key: str) -> list[str]:
        v = rude.get(key)
        if v is None:
            return []
        return [str(x) for x in (v if isinstance(v, list) else [v])]

    return Config(
        select=get_list("select"),
        ignore=get_list("ignore"),
        plugins=get_list("plugins"),
        local_rules=get_list("local-rules"),
        rule_options=rules if isinstance(rules, dict) else {},
        config_path=path,
    )


__all__ = ["Config", "find_config_file", "load_config"]
