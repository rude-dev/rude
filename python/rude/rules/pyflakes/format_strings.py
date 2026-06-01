"""
Format string rules for .format() and % formatting.

.format() rules:
F521: StringDotFormatInvalidFormat - invalid format string
F522: StringDotFormatExtraNamedArguments - unused named arguments
F523: StringDotFormatExtraPositionalArguments - unused positional arguments
F524: StringDotFormatMissingArgument - missing argument
F525: StringDotFormatMixingAutomatic - mixing auto and manual numbering

% formatting rules:
F501: PercentFormatInvalidFormat - invalid format string
F502: PercentFormatExpectedMapping - expected mapping, got sequence
F503: PercentFormatExpectedSequence - expected sequence, got mapping
F504: PercentFormatExtraNamedArguments - unused named arguments
F505: PercentFormatMissingArgument - missing argument
F506: PercentFormatMixedPositionalAndNamed - mixing positional and named
F507: PercentFormatPositionalCountMismatch - wrong number of arguments
F508: PercentFormatStarRequiresSequence - * requires sequence
F509: PercentFormatUnsupportedFormatCharacter - unsupported format character
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from rude.core.node_types import NodeType
from rude.core.rule import Rule
from rude.core.types import Diagnostic, Severity

if TYPE_CHECKING:
    from rude.core.node import Node


# ─────────────────────────────────────────────────────────────────────────────
# .format() Parser
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class FormatField:
    """A field in a .format() string."""

    name: str | int | None  # None = auto, int = positional, str = named
    conversion: str | None  # !r, !s, !a
    format_spec: str | None


def parse_format_string(fmt: str) -> tuple[list[FormatField], str | None]:
    """
    Parse a .format() format string.

    Returns (fields, error_message).
    """
    fields: list[FormatField] = []
    error: str | None = None
    i = 0

    while i < len(fmt):
        if fmt[i] == "{":
            if i + 1 < len(fmt) and fmt[i + 1] == "{":
                # Escaped brace
                i += 2
                continue

            # Find matching }
            depth = 1
            start = i + 1
            i += 1
            while i < len(fmt) and depth > 0:
                if fmt[i] == "{":
                    depth += 1
                elif fmt[i] == "}":
                    depth -= 1
                i += 1

            if depth > 0:
                error = "unmatched '{'"
                break

            field_text = fmt[start : i - 1]
            field, field_error = _parse_format_field(field_text)
            if field_error:
                error = field_error
                break
            fields.append(field)

        elif fmt[i] == "}":
            if i + 1 < len(fmt) and fmt[i + 1] == "}":
                # Escaped brace
                i += 2
                continue
            error = "single '}' encountered in format string"
            break
        else:
            i += 1

    return fields, error


def _parse_format_field(text: str) -> tuple[FormatField, str | None]:
    """Parse a single format field (content between {})."""
    # Format: [field_name][!conversion][:format_spec]
    name: str | int | None = None
    conversion: str | None = None
    format_spec: str | None = None

    # Check for conversion
    conv_idx = text.find("!")
    spec_idx = text.find(":")

    if conv_idx != -1 and (spec_idx == -1 or conv_idx < spec_idx):
        # Has conversion
        if spec_idx != -1:
            conversion = text[conv_idx + 1 : spec_idx]
            format_spec = text[spec_idx + 1 :]
            text = text[:conv_idx]
        else:
            conversion = text[conv_idx + 1 :]
            text = text[:conv_idx]

        if conversion not in ("r", "s", "a"):
            return FormatField(None, None, None), f"unknown conversion specifier {conversion!r}"
    elif spec_idx != -1:
        format_spec = text[spec_idx + 1 :]
        text = text[:spec_idx]

    # Parse field name
    if not text:
        name = None  # Auto-numbering
    elif text.isdigit():
        name = int(text)
    else:
        # Could be name or name.attr or name[key]
        # Extract the base name
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)", text)
        if match:
            name = match.group(1)
        elif text[0].isdigit():
            # Like "0.attr"
            match = re.match(r"^(\d+)", text)
            if match:
                name = int(match.group(1))

    return FormatField(name, conversion, format_spec), None


# ─────────────────────────────────────────────────────────────────────────────
# % Format Parser
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PercentField:
    """A field in a % format string."""

    key: str | None  # %(name)s -> "name"
    flags: str
    width: str
    precision: str
    conversion: str  # s, d, f, etc.


# Valid conversion specifiers for % formatting
PERCENT_CONVERSIONS = frozenset("diouxXeEfFgGcrsab%")


def parse_percent_format(fmt: str) -> tuple[list[PercentField], str | None]:
    """
    Parse a % format string.

    Returns (fields, error_message).
    """
    fields: list[PercentField] = []
    error: str | None = None

    # Regex for % format specifiers
    # %(name)flags.precision_conversion
    pattern = re.compile(
        r"%"
        r"(?:\(([^)]+)\))?"  # (name)
        r"([#0\- +]*)?"  # flags
        r"(\*|\d+)?"  # width
        r"(?:\.(\*|\d+))?"  # .precision
        r"([hlL])?"  # length modifier (ignored)
        r"(.)"  # conversion type
    )

    for match in pattern.finditer(fmt):
        key = match.group(1)
        flags = match.group(2) or ""
        width = match.group(3) or ""
        precision = match.group(4) or ""
        conversion = match.group(6)

        if conversion == "%":
            continue  # %% is literal %

        if conversion not in PERCENT_CONVERSIONS:
            error = f"unsupported format character {conversion!r}"
            break

        fields.append(PercentField(key, flags, width, precision, conversion))

    return fields, error


# ─────────────────────────────────────────────────────────────────────────────
# Shared Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _get_string_value(node: Node) -> str | None:
    """Extract the string value from a string literal node."""
    text = node.text
    if not text:
        return None
    if text.startswith('"""') or text.startswith("'''"):
        return text[3:-3]
    elif text.startswith('"') or text.startswith("'"):
        return text[1:-1]
    elif text.startswith('f"') or text.startswith("f'"):
        return text[2:-1]
    return None


def _is_format_call(node: Node) -> bool:
    """Check if this is a str.format() call."""
    if not node.is_call:
        return False
    func = node.child_by_field("function")
    if not func or not func.is_attribute:
        return False
    attr = func.child_by_field("attribute")
    return attr is not None and attr.text == "format"


def _is_percent_format(node: Node) -> bool:
    """Check if this is a % string formatting operation."""
    operator = node.child_by_field("operator")
    if operator and operator.text == "%":
        left = node.child_by_field("left")
        return left is not None and left.type == "string"
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Rules
# ─────────────────────────────────────────────────────────────────────────────


class StringDotFormatInvalidFormat(Rule):
    """
    F521: Invalid .format() format string.

    Rationale: An invalid format string causes a ``ValueError`` at
    runtime.

    Example::

        # Bad
        "{".format()     # F521 - unclosed brace
        "{0!z}".format() # F521 - unknown conversion

        # Good
        "{}".format(value)
    """

    code: ClassVar[str] = "F521"
    message: ClassVar[str] = "format string has invalid format: {error}"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.CALL}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_format_call(node):
            return

        func = node.child_by_field("function")
        if not func or not func.is_attribute:
            return

        obj = func.child_by_field("object")
        if not obj or obj.type != "string":
            return

        fmt_string = _get_string_value(obj)
        if fmt_string is None:
            return

        _, error = parse_format_string(fmt_string)
        if error:
            yield self.diagnostic(obj, self.message.format(error=error))


class StringDotFormatMixingAutomatic(Rule):
    """
    F525: Mixing automatic and manual field numbering in .format().

    Rationale: Python does not allow mixing automatic (``{}``) and manual
    (``{0}``) field numbering, raising a ``ValueError`` at runtime.

    Example::

        # Bad
        "{} {0}".format(a, b)  # F525 - mixing auto and manual

        # Good
        "{} {}".format(a, b)   # all auto
        "{0} {1}".format(a, b) # all manual
    """

    code: ClassVar[str] = "F525"
    message: ClassVar[str] = "format string mixes automatic and manual field specification"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.CALL}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_format_call(node):
            return

        func = node.child_by_field("function")
        if not func or not func.is_attribute:
            return

        obj = func.child_by_field("object")
        if not obj or obj.type != "string":
            return

        fmt_string = _get_string_value(obj)
        if fmt_string is None:
            return

        fields, error = parse_format_string(fmt_string)
        if error:
            return  # F521 will handle this

        has_auto = False
        has_manual = False

        for field in fields:
            if field.name is None:
                has_auto = True
            elif isinstance(field.name, int):
                has_manual = True

        if has_auto and has_manual:
            yield self.diagnostic(obj)


class StringDotFormatExtraPositionalArguments(Rule):
    """
    F523: .format() call has unused positional arguments.

    Rationale: Extra arguments are silently ignored, which usually
    indicates a bug in the format string.

    Example::

        # Bad
        "{0}".format(a, b, c)  # F523 - b and c are unused

        # Good
        "{0} {1} {2}".format(a, b, c)
    """

    code: ClassVar[str] = "F523"
    message: ClassVar[str] = "format string has {count} unused positional argument(s)"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.CALL}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_format_call(node):
            return

        func = node.child_by_field("function")
        if not func or not func.is_attribute:
            return

        obj = func.child_by_field("object")
        if not obj or obj.type != "string":
            return

        fmt_string = _get_string_value(obj)
        if fmt_string is None:
            return

        fields, error = parse_format_string(fmt_string)
        if error:
            return

        # Get arguments
        args = node.child_by_field("arguments")
        if not args:
            return

        positional_count = 0
        for arg in args.named_children:
            if arg.type == "keyword_argument":
                break
            if arg.type not in ("*", "**"):
                positional_count += 1

        # Count used positional indices
        used_indices: set[int] = set()
        auto_index = 0

        for field in fields:
            if field.name is None:
                used_indices.add(auto_index)
                auto_index += 1
            elif isinstance(field.name, int):
                used_indices.add(field.name)

        max_used = max(used_indices) + 1 if used_indices else 0
        unused = positional_count - max_used

        if unused > 0:
            yield self.diagnostic(node, self.message.format(count=unused))


class StringDotFormatExtraNamedArguments(Rule):
    """
    F522: .format() call has unused named arguments.

    Rationale: Extra named arguments are silently ignored, which
    usually indicates a bug in the format string.

    Example::

        # Bad
        "{name}".format(name=a, other=b)  # F522 - other is unused

        # Good
        "{name}".format(name=a)
    """

    code: ClassVar[str] = "F522"
    message: ClassVar[str] = "format string has unused named argument(s): {names}"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.CALL}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_format_call(node):
            return

        func = node.child_by_field("function")
        if not func or not func.is_attribute:
            return

        obj = func.child_by_field("object")
        if not obj or obj.type != "string":
            return

        fmt_string = _get_string_value(obj)
        if fmt_string is None:
            return

        fields, error = parse_format_string(fmt_string)
        if error:
            return

        # Get named arguments
        args = node.child_by_field("arguments")
        if not args:
            return

        provided_names: set[str] = set()
        for arg in args.named_children:
            if arg.type == "keyword_argument":
                name = arg.child_by_field("name")
                if name:
                    provided_names.add(name.text)

        # Get used names from format string
        used_names: set[str] = set()
        for field in fields:
            if isinstance(field.name, str):
                used_names.add(field.name)

        unused = provided_names - used_names
        if unused:
            yield self.diagnostic(node, self.message.format(names=", ".join(sorted(unused))))


class StringDotFormatMissingArgument(Rule):
    """
    F524: .format() call is missing arguments.

    Rationale: Missing arguments cause a ``KeyError`` or ``IndexError``
    at runtime.

    Example::

        # Bad
        "{0} {1}".format(a)  # F524 - missing argument 1
        "{name}".format()    # F524 - missing argument 'name'

        # Good
        "{0} {1}".format(a, b)
    """

    code: ClassVar[str] = "F524"
    message: ClassVar[str] = "format string is missing argument(s): {missing}"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.CALL}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_format_call(node):
            return

        func = node.child_by_field("function")
        if not func or not func.is_attribute:
            return

        obj = func.child_by_field("object")
        if not obj or obj.type != "string":
            return

        fmt_string = _get_string_value(obj)
        if fmt_string is None:
            return

        fields, error = parse_format_string(fmt_string)
        if error:
            return

        # Get arguments
        args = node.child_by_field("arguments")
        positional_count = 0
        named_args: set[str] = set()

        if args:
            for arg in args.named_children:
                if arg.type == "keyword_argument":
                    name = arg.child_by_field("name")
                    if name:
                        named_args.add(name.text)
                elif arg.type not in ("*", "**"):
                    positional_count += 1

        # Check required arguments
        missing: list[str] = []
        auto_index = 0

        for field in fields:
            if field.name is None:
                if auto_index >= positional_count:
                    missing.append(str(auto_index))
                auto_index += 1
            elif isinstance(field.name, int):
                if field.name >= positional_count:
                    missing.append(str(field.name))
            elif isinstance(field.name, str):
                if field.name not in named_args:
                    missing.append(repr(field.name))

        if missing:
            yield self.diagnostic(node, self.message.format(missing=", ".join(missing)))


# ─────────────────────────────────────────────────────────────────────────────
# % Format Rules
# ─────────────────────────────────────────────────────────────────────────────


class PercentFormatInvalidFormat(Rule):
    """
    F501: Invalid % format string.

    Rationale: An invalid format specifier causes a ``ValueError`` at
    runtime.

    Example::

        # Bad
        "%z" % x  # F501 - z is not a valid format character

        # Good
        "%s" % x
    """

    code: ClassVar[str] = "F501"
    message: ClassVar[str] = "percent format has invalid format string: {error}"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.BINARY_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_percent_format(node):
            return

        left = node.child_by_field("left")
        if not left or left.type != "string":
            return

        fmt_string = _get_string_value(left)
        if fmt_string is None:
            return

        _, error = parse_percent_format(fmt_string)
        if error:
            yield self.diagnostic(left, self.message.format(error=error))


class PercentFormatExpectedMapping(Rule):
    """
    F502: % format expected mapping but got sequence.

    Rationale: Named placeholders like ``%(name)s`` require a mapping
    (dict), not a sequence. This causes a ``TypeError`` at runtime.

    Example::

        # Bad
        "%(name)s" % (1, 2)  # F502 - expected dict, got tuple

        # Good
        "%(name)s" % {"name": "Alice"}
    """

    code: ClassVar[str] = "F502"
    message: ClassVar[str] = "percent format expected mapping but found sequence"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.BINARY_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_percent_format(node):
            return

        left = node.child_by_field("left")
        if not left or left.type != "string":
            return

        fmt_string = _get_string_value(left)
        if fmt_string is None:
            return

        fields, error = parse_percent_format(fmt_string)
        if error:
            return

        # Check if format uses named fields
        uses_named = any(f.key is not None for f in fields)

        if not uses_named:
            return

        # Check right side
        right = node.child_by_field("right")
        if right and right.type in ("tuple", "list"):
            yield self.diagnostic(node)


class PercentFormatExpectedSequence(Rule):
    """
    F503: % format expected sequence but got mapping.

    Rationale: Positional placeholders like ``%s`` require a sequence
    (tuple), not a mapping. This causes a ``TypeError`` at runtime.

    Example::

        # Bad
        "%s %s" % {"a": 1}  # F503 - expected tuple, got dict

        # Good
        "%s %s" % (1, 2)
    """

    code: ClassVar[str] = "F503"
    message: ClassVar[str] = "percent format expected sequence but found mapping"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.BINARY_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_percent_format(node):
            return

        left = node.child_by_field("left")
        if not left or left.type != "string":
            return

        fmt_string = _get_string_value(left)
        if fmt_string is None:
            return

        fields, error = parse_percent_format(fmt_string)
        if error:
            return

        # Check if format uses positional fields
        uses_positional = any(f.key is None for f in fields)
        uses_named = any(f.key is not None for f in fields)

        # If format has more than one positional field and no named fields
        if uses_positional and not uses_named and len(fields) > 1:
            # Check right side
            right = node.child_by_field("right")
            if right and right.type == "dictionary":
                yield self.diagnostic(node)


class PercentFormatMixedPositionalAndNamed(Rule):
    """
    F506: % format mixes positional and named placeholders.

    Rationale: Python does not support mixing positional and named
    placeholders in ``%``-formatting. This causes a ``TypeError``.

    Example::

        # Bad
        "%s %(name)s" % (1, {"name": 2})  # F506 - can't mix

        # Good
        "%(first)s %(name)s" % {"first": 1, "name": 2}
    """

    code: ClassVar[str] = "F506"
    message: ClassVar[str] = "percent format has mixed positional and named placeholders"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.BINARY_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_percent_format(node):
            return

        left = node.child_by_field("left")
        if not left or left.type != "string":
            return

        fmt_string = _get_string_value(left)
        if fmt_string is None:
            return

        fields, error = parse_percent_format(fmt_string)
        if error:
            return

        has_positional = any(f.key is None for f in fields)
        has_named = any(f.key is not None for f in fields)

        if has_positional and has_named:
            yield self.diagnostic(left)


class PercentFormatUnsupportedCharacter(Rule):
    """
    F509: % format has unsupported format character.

    Rationale: Using an unsupported conversion character causes a
    ``ValueError`` at runtime.

    Example::

        # Bad
        "%z" % x  # F509 - z is not a valid format character

        # Good
        "%s" % x
    """

    code: ClassVar[str] = "F509"
    message: ClassVar[str] = "percent format has unsupported format character '{char}'"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.BINARY_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_percent_format(node):
            return

        left = node.child_by_field("left")
        if not left or left.type != "string":
            return

        fmt_string = _get_string_value(left)
        if fmt_string is None:
            return

        _, error = parse_percent_format(fmt_string)
        if error and "unsupported format character" in error:
            # Extract the character from error message
            char = error.split("'")[1] if "'" in error else "?"
            yield self.diagnostic(left, self.message.format(char=char))


class PercentFormatPositionalCountMismatch(Rule):
    """
    F507: % format positional argument count mismatch.

    Rationale: Providing the wrong number of arguments causes a
    ``TypeError`` at runtime.

    Example::

        # Bad
        "%s %s" % (1,)  # F507 - expected 2 arguments, got 1

        # Good
        "%s %s" % (1, 2)
    """

    code: ClassVar[str] = "F507"
    message: ClassVar[str] = "percent format expected {expected} argument(s) but found {found}"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.BINARY_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_percent_format(node):
            return

        left = node.child_by_field("left")
        if not left or left.type != "string":
            return

        fmt_string = _get_string_value(left)
        if fmt_string is None:
            return

        fields, error = parse_percent_format(fmt_string)
        if error:
            return

        # Only check positional formats (no named fields)
        if any(f.key is not None for f in fields):
            return

        # Skip if any field uses `*` for width/precision: argument count is dynamic.
        if any(f.width == "*" or f.precision == "*" for f in fields):
            return

        # Pyflakes only checks F507 against a tuple literal RHS; a variable
        # cannot be counted statically without speculating about runtime values.
        right = node.child_by_field("right")
        if not right or right.type != "tuple":
            return

        expected = len(fields)
        found = len(list(right.named_children))

        if expected != found:
            yield self.diagnostic(
                node,
                self.message.format(expected=expected, found=found),
            )


class PercentFormatExtraNamedArguments(Rule):
    """
    F504: % format has unused named arguments.

    Rationale: Extra keys in the mapping are silently ignored, which
    usually indicates a bug in the format string.

    Example::

        # Bad
        "%(name)s" % {"name": 1, "other": 2}  # F504 - other is unused

        # Good
        "%(name)s" % {"name": 1}
    """

    code: ClassVar[str] = "F504"
    message: ClassVar[str] = "percent format has unused named argument(s): {names}"
    severity: ClassVar[Severity] = Severity.WARNING
    node_types = {NodeType.BINARY_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_percent_format(node):
            return

        left = node.child_by_field("left")
        if not left or left.type != "string":
            return

        fmt_string = _get_string_value(left)
        if fmt_string is None:
            return

        fields, error = parse_percent_format(fmt_string)
        if error:
            return

        # Only check named formats
        required_keys = {f.key for f in fields if f.key is not None}
        if not required_keys:
            return

        # Get right side - must be a dict literal
        right = node.child_by_field("right")
        if not right or right.type != "dictionary":
            return

        # Extract keys from dict
        provided_keys: set[str] = set()
        for child in right.named_children:
            if child.type == "pair":
                key = child.child_by_field("key")
                if key and key.type == "string":
                    key_val = _get_string_value(key)
                    if key_val:
                        provided_keys.add(key_val)

        unused = provided_keys - required_keys
        if unused:
            yield self.diagnostic(node, self.message.format(names=", ".join(sorted(unused))))


class PercentFormatMissingArgument(Rule):
    """
    F505: % format is missing named argument.

    Rationale: A missing key causes a ``KeyError`` at runtime.

    Example::

        # Bad
        "%(name)s %(other)s" % {"name": 1}  # F505 - missing 'other'

        # Good
        "%(name)s %(other)s" % {"name": 1, "other": 2}
    """

    code: ClassVar[str] = "F505"
    message: ClassVar[str] = "percent format is missing argument(s): {missing}"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.BINARY_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_percent_format(node):
            return

        left = node.child_by_field("left")
        if not left or left.type != "string":
            return

        fmt_string = _get_string_value(left)
        if fmt_string is None:
            return

        fields, error = parse_percent_format(fmt_string)
        if error:
            return

        # Only check named formats
        required_keys = {f.key for f in fields if f.key is not None}
        if not required_keys:
            return

        # Get right side - must be a dict literal
        right = node.child_by_field("right")
        if not right or right.type != "dictionary":
            return

        # Extract keys from dict
        provided_keys: set[str] = set()
        for child in right.named_children:
            if child.type == "pair":
                key = child.child_by_field("key")
                if key and key.type == "string":
                    key_val = _get_string_value(key)
                    if key_val:
                        provided_keys.add(key_val)

        missing = required_keys - provided_keys
        if missing:
            yield self.diagnostic(node, self.message.format(missing=", ".join(sorted(missing))))


class PercentFormatStarRequiresSequence(Rule):
    """
    F508: % format with * width/precision requires sequence.

    Rationale: The ``*`` specifier reads width/precision from the
    argument tuple, so a mapping cannot be used.

    Example::

        # Bad
        "%*s" % {"width": 5}  # F508 - * requires positional args

        # Good
        "%*s" % (10, "hello")
    """

    code: ClassVar[str] = "F508"
    message: ClassVar[str] = "percent format with * width/precision requires sequence argument"
    severity: ClassVar[Severity] = Severity.ERROR
    node_types = {NodeType.BINARY_OPERATOR}

    def check(self, node: Node) -> Iterator[Diagnostic]:
        if not _is_percent_format(node):
            return

        left = node.child_by_field("left")
        if not left or left.type != "string":
            return

        fmt_string = _get_string_value(left)
        if fmt_string is None:
            return

        fields, error = parse_percent_format(fmt_string)
        if error:
            return

        # Check if any field uses * for width or precision
        uses_star = any(f.width == "*" or f.precision == "*" for f in fields)
        if not uses_star:
            return

        # Get right side - if it's a dict, that's an error
        right = node.child_by_field("right")
        if right and right.type == "dictionary":
            yield self.diagnostic(node)


FORMAT_STRING_RULES = [
    StringDotFormatInvalidFormat,
    StringDotFormatMixingAutomatic,
    StringDotFormatExtraPositionalArguments,
    StringDotFormatExtraNamedArguments,
    StringDotFormatMissingArgument,
    PercentFormatInvalidFormat,
    PercentFormatMixedPositionalAndNamed,
    PercentFormatUnsupportedCharacter,
    PercentFormatPositionalCountMismatch,
    PercentFormatExtraNamedArguments,
    PercentFormatMissingArgument,
    PercentFormatExpectedMapping,
    PercentFormatExpectedSequence,
    PercentFormatStarRequiresSequence,
]

__all__ = [
    # All rules
    "FORMAT_STRING_RULES",
    "PercentFormatExpectedMapping",
    "PercentFormatExpectedSequence",
    "PercentFormatExtraNamedArguments",
    # % format rules
    "PercentFormatInvalidFormat",
    "PercentFormatMissingArgument",
    "PercentFormatMixedPositionalAndNamed",
    "PercentFormatPositionalCountMismatch",
    "PercentFormatStarRequiresSequence",
    "PercentFormatUnsupportedCharacter",
    "StringDotFormatExtraNamedArguments",
    "StringDotFormatExtraPositionalArguments",
    # .format() rules
    "StringDotFormatInvalidFormat",
    "StringDotFormatMissingArgument",
    "StringDotFormatMixingAutomatic",
]
