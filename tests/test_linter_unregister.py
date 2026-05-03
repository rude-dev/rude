from collections.abc import Iterator
from typing import ClassVar

from rude.core.linter import Linter
from rude.core.node_types import NodeType
from rude.core.rule import LineRule, Rule
from rude.core.types import Diagnostic, FileContext


class DummyRule(Rule):
    code: ClassVar[str] = "TEST001"
    message: ClassVar[str] = "test"
    node_types = {NodeType.CALL}

    def check(self, node: object) -> Iterator[Diagnostic]:
        return iter(())


class DummyLineRule(LineRule):
    code: ClassVar[str] = "TEST002"
    message: ClassVar[str] = "test line"

    def check_line(
        self,
        line: str,
        lineno: int,
        ctx: FileContext,
        *,
        comment_pos: int = -1,
    ) -> Iterator[Diagnostic]:
        return iter(())


def test_unregister_rule() -> None:
    linter = Linter()
    linter.register(DummyRule())
    assert linter.unregister("TEST001") is True
    assert linter.get_rule("TEST001") is None


def test_unregister_line_rule() -> None:
    linter = Linter()
    linter.register(DummyLineRule())
    assert linter.unregister("TEST002") is True
    assert linter.get_rule("TEST002") is None


def test_unregister_nonexistent() -> None:
    linter = Linter()
    assert linter.unregister("NOPE") is False
