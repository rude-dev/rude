"""Rule discovery from built-in, plugins, and local sources."""

from __future__ import annotations

import sys
import warnings
from importlib import import_module
from importlib.metadata import entry_points
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rude.core.rule import RuleBase


class RuleDiscovery:
    """Discovers rules from all configured sources."""

    def discover_all(
        self,
        *,
        select: list[str] | None = None,
        ignore: list[str] | None = None,
        plugins: list[str] | None = None,
        local_rules: list[str] | None = None,
        load_entry_points: bool = True,
    ) -> list[RuleBase]:
        """Discover and instantiate all rules."""
        classes: list[type[RuleBase]] = []

        classes.extend(self.load_builtin())
        if load_entry_points:
            classes.extend(self.load_entry_points())
        for p in plugins or []:
            classes.extend(self.load_plugin(p))
        for p in local_rules or []:
            classes.extend(self.load_local(p))

        filtered = self._filter(classes, select, ignore)
        return [cls() for cls in filtered]

    def load_builtin(self) -> list[type[RuleBase]]:
        try:
            from rude.rules import ALL_RULES

            return list(ALL_RULES)
        except ImportError:
            return []

    def load_entry_points(self) -> list[type[RuleBase]]:
        result: list[type[RuleBase]] = []
        eps = entry_points(group="rude.plugins")
        for ep in eps:
            try:
                mod = ep.load()
                if hasattr(mod, "RULES"):
                    result.extend(mod.RULES)
            except Exception as e:
                warnings.warn(f"Plugin {ep.name} failed: {e}", stacklevel=2)
        return result

    def load_plugin(self, name: str) -> list[type[RuleBase]]:
        mod_name = name.replace("-", "_")
        try:
            mod = import_module(mod_name)
            return list(getattr(mod, "RULES", []))
        except ImportError as e:
            warnings.warn(f"Plugin {name}: {e}", stacklevel=2)
            return []

    def load_local(self, path: str | Path) -> list[type[RuleBase]]:
        path = Path(path)
        if not path.exists():
            warnings.warn(f"Local rules not found: {path}", stacklevel=2)
            return []
        if path.is_file():
            return self._load_file(path)
        result: list[type[RuleBase]] = []
        for f in sorted(path.glob("*.py")):
            if not f.name.startswith("_"):
                result.extend(self._load_file(f))
        return result

    def _load_file(self, path: Path) -> list[type[RuleBase]]:
        from rude.core.rule import Rule

        mod_name = f"rude_local_{path.stem}_{id(path)}"
        try:
            spec = spec_from_file_location(mod_name, path)
            if not spec or not spec.loader:
                return []
            mod = module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
            if hasattr(mod, "RULES"):
                return list(mod.RULES)
            return [
                obj
                for name in dir(mod)
                for obj in [getattr(mod, name)]
                if isinstance(obj, type)
                and issubclass(obj, Rule)
                and obj is not Rule
                and hasattr(obj, "code")
            ]
        except Exception as e:
            warnings.warn(f"Local rules {path}: {e}", stacklevel=2)
            return []

    @staticmethod
    def _prefix_matches(code: str, prefix: str) -> bool:
        """Check if *prefix* selects *code*.

        A prefix matches when the code starts with it AND the next character
        (if any) is a digit.  This prevents ``E`` from matching ``EX001`` while
        still allowing ``E7`` to match ``E711``.
        """
        if not code.startswith(prefix):
            return False
        # Exact match or next char is a digit → same category.
        return len(code) == len(prefix) or code[len(prefix)].isdigit()

    def _filter(
        self, classes: list[type[RuleBase]], select: list[str] | None, ignore: list[str] | None
    ) -> list[type[RuleBase]]:
        if select is None and ignore is None:
            return classes
        if select is not None:
            selected = {
                c
                for c in classes
                for p in select
                if self._prefix_matches(c.code.upper(), p.upper())
            }
        else:
            selected = set(classes)
        for p in ignore or []:
            selected = {c for c in selected if not self._prefix_matches(c.code.upper(), p.upper())}
        return [c for c in classes if c in selected]


def discover_rules(
    *,
    select: list[str] | None = None,
    ignore: list[str] | None = None,
    plugins: list[str] | None = None,
    local_rules: list[str] | None = None,
    load_entry_points: bool = True,
) -> list[RuleBase]:
    return RuleDiscovery().discover_all(
        select=select,
        ignore=ignore,
        plugins=plugins,
        local_rules=local_rules,
        load_entry_points=load_entry_points,
    )


__all__ = ["RuleDiscovery", "discover_rules"]
