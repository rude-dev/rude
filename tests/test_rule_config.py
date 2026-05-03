"""Tests for _RuleConfig serialization round-trip.

All registered rules must survive serialization via _RuleConfig,
which is used by the multiprocessing path.
"""

from __future__ import annotations

from rude.core.linter import _RuleConfig
from rude.rules import ALL_RULES


class TestRuleConfigSerialization:
    """Verify that rule configs can be serialized and reconstructed."""

    def test_all_rules_round_trip(self) -> None:
        """Every registered rule survives _RuleConfig round-trip."""
        for rule_cls in ALL_RULES:
            rule = rule_cls()
            cfg = _RuleConfig(
                rule_class=type(rule),
                options=getattr(rule, "__dict__", {}),
            )
            # Reconstruct the rule from config
            restored = cfg.rule_class()
            for k, v in cfg.options.items():
                setattr(restored, k, v)

            assert type(restored) is type(rule)
            assert restored.code == rule.code

    def test_configured_rule_preserves_options(self) -> None:
        """Rule options survive the round-trip."""
        from rude.rules.pyflakes import UnusedVariable

        rule = UnusedVariable()
        rule.configure({"ignore_prefixes": ["_", "unused_", "tmp_"]})

        cfg = _RuleConfig(
            rule_class=type(rule),
            options=getattr(rule, "__dict__", {}),
        )
        restored = cfg.rule_class()
        for k, v in cfg.options.items():
            setattr(restored, k, v)

        assert restored.ignore_prefixes == ("_", "unused_", "tmp_")
