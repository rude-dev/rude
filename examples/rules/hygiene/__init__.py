"""
Hygiene rules - code hygiene checks.

Rules about the codebase itself: noqa comments, TODOs, etc.
Enable via select = ["META"].
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any, ClassVar

from rude.core.node import Node
from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Severity


class TodoWithoutTicket(Rule):
    """
    Require TODO/FIXME comments to reference a ticket.

    Rationale: Untracked TODOs tend to be forgotten. Linking to a
    ticket ensures follow-up.

    Config:
        [tool.rude.rules.META001]
        ticket_pattern = "(JIRA-\\d+|#\\d+|TODO\\(\\w+\\))"

    Example::

        # Bad
        # TODO: fix this later

        # Good
        # TODO(JIRA-123): fix this later
    """

    code: ClassVar[str] = "META001"
    message: ClassVar[str] = "TODO/FIXME without ticket reference"
    severity: ClassVar[Severity] = Severity.INFO
    node_types = {NodeType.COMMENT}

    ticket_pattern: str = r"(JIRA-\d+|#\d+|TODO\(\w+\))"

    def configure(self, options: dict[str, Any]) -> None:
        self.ticket_pattern = options.get("ticket_pattern", self.ticket_pattern)

    def check(self, node: Node) -> Iterator[Diagnostic]:
        text = node.text.upper()
        if "TODO" not in text and "FIXME" not in text and "HACK" not in text:
            return
        if not re.search(self.ticket_pattern, node.text, re.IGNORECASE):
            yield self.diagnostic(node)


class BlanketNoqa(Rule):
    """Flag blanket # noqa without specific codes.

    Rationale: Blanket ``# noqa`` silences all warnings on a line,
    hiding real issues. Always specify which codes to suppress.

    Example::

        # Bad
        x = eval(input)  # noqa

        # Good
        x = eval(input)  # noqa: PAT008
    """

    code: ClassVar[str] = "META002"
    message: ClassVar[str] = "Blanket noqa; specify codes: # noqa: CODE1,CODE2"
    severity: ClassVar[Severity] = Severity.INFO
    node_types = {NodeType.COMMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        text = node.text.lower()
        if "# noqa" not in text:
            return
        # Check if it has codes
        match = re.search(r"#\s*noqa(?::?\s*([A-Z0-9,\s]+))?", node.text, re.IGNORECASE)
        if match and not match.group(1):
            yield self.diagnostic(node)


class TypeIgnoreWithoutCode(Rule):
    """Flag type: ignore without specific codes.

    Rationale: Blanket ``type: ignore`` suppresses all type errors,
    hiding real issues. Always specify the mypy error code.

    Example::

        # Bad
        x = foo()  # type: ignore

        # Good
        x = foo()  # type: ignore[no-untyped-call]
    """

    code: ClassVar[str] = "META003"
    message: ClassVar[str] = "Blanket type: ignore; specify error codes"
    severity: ClassVar[Severity] = Severity.INFO
    node_types = {NodeType.COMMENT}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        text = node.text
        if "type:" not in text.lower() or "ignore" not in text.lower():
            return
        # Check if it has codes in brackets
        if re.search(r"type:\s*ignore\s*\[", text, re.IGNORECASE):
            return  # Has codes
        if re.search(r"type:\s*ignore\s*$", text.strip(), re.IGNORECASE):
            yield self.diagnostic(node)


RULES = [TodoWithoutTicket, BlanketNoqa, TypeIgnoreWithoutCode]
