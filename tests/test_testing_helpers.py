"""Tests for rude.testing wrappers: options= and filename= forwarding."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, ClassVar

from rude.core.node import Node
from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Fix
from rude.testing import (
    assert_error,
    assert_error_count,
    assert_fix,
    assert_no_errors,
    assert_no_fix,
    check_codes,
    check_source,
    fix_source,
)


class _OptionsCapturingRule(Rule):
    """No-op rule that records every options dict passed to configure()."""

    code = "TEST001"
    message = "captured"
    node_types: ClassVar[set[NodeType] | None] = {NodeType.MODULE}
    received: ClassVar[list[dict[str, Any]]] = []

    def configure(self, options: dict[str, Any]) -> None:
        self.__class__.received.append(options)

    def check(self, node: Node) -> Iterator[Diagnostic]:
        return iter(())


class _FilenameReportingRule(Rule):
    """Yields a diagnostic whose message is ctx.path -- used to assert filename plumbing."""

    code = "PATH001"
    message = ""
    node_types: ClassVar[set[NodeType] | None] = {NodeType.MODULE}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        yield self.diagnostic(node, message=str(node.ctx.path))


class _FixableModuleRule(Rule):
    """Yields a deletion fix on the module node -- used to assert fix wrappers."""

    code = "FIX001"
    message = "delete"
    node_types: ClassVar[set[NodeType] | None] = {NodeType.MODULE}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        yield self.diagnostic(node, fix=Fix.replace(node, ""))


class TestCheckSource:
    def test_options_forwarded_to_configure(self):
        _OptionsCapturingRule.received.clear()
        check_source(_OptionsCapturingRule, "x = 1\n", options={"foo": "bar"})
        assert _OptionsCapturingRule.received == [{"foo": "bar"}]

    def test_no_configure_when_options_none(self):
        _OptionsCapturingRule.received.clear()
        check_source(_OptionsCapturingRule, "x = 1\n")
        assert _OptionsCapturingRule.received == []

    def test_filename_forwarded_to_ctx_path(self):
        diags = check_source(_FilenameReportingRule, "x = 1\n", filename="custom.py")
        assert len(diags) == 1
        assert diags[0].message == "custom.py"


class TestFixSource:
    def test_options_forwarded(self):
        _OptionsCapturingRule.received.clear()
        fix_source(_OptionsCapturingRule, "x = 1\n", options={"k": 1})
        assert _OptionsCapturingRule.received == [{"k": 1}]

    def test_filename_forwarded(self):
        diags, _ = fix_source(_FilenameReportingRule, "x = 1\n", filename="other.py")
        assert len(diags) == 1
        assert diags[0].message == "other.py"


class TestWrappersAcceptKwargs:
    """Smoke check: every public wrapper accepts options= and filename= without raising."""

    def test_check_codes(self):
        _OptionsCapturingRule.received.clear()
        codes = check_codes(_OptionsCapturingRule, "x = 1\n", options={"a": 1}, filename="t.py")
        assert codes == []
        assert _OptionsCapturingRule.received == [{"a": 1}]

    def test_assert_no_errors(self):
        _OptionsCapturingRule.received.clear()
        assert_no_errors(_OptionsCapturingRule, "x = 1\n", options={"a": 1}, filename="t.py")
        assert _OptionsCapturingRule.received == [{"a": 1}]

    def test_assert_error(self):
        diags = assert_error(_FilenameReportingRule, "x = 1\n", filename="t.py")
        assert diags[0].message == "t.py"

    def test_assert_error_count(self):
        diags = assert_error_count(_FilenameReportingRule, "x = 1\n", 1, filename="t.py")
        assert diags[0].message == "t.py"

    def test_assert_fix(self):
        _ = assert_fix(_FixableModuleRule, "x = 1\n", "", filename="t.py")

    def test_assert_no_fix(self):
        _ = assert_no_fix(_OptionsCapturingRule, "x = 1\n", options={}, filename="t.py")
