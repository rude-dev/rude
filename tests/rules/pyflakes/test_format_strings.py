"""Tests for format string rules (F521-F525, F501-F509)."""

from rude.rules.pyflakes import (
    PercentFormatExpectedMapping,
    PercentFormatExpectedSequence,
    PercentFormatExtraNamedArguments,
    PercentFormatInvalidFormat,
    PercentFormatMissingArgument,
    PercentFormatMixedPositionalAndNamed,
    PercentFormatPositionalCountMismatch,
    PercentFormatStarRequiresSequence,
    PercentFormatUnsupportedCharacter,
    StringDotFormatExtraNamedArguments,
    StringDotFormatExtraPositionalArguments,
    StringDotFormatInvalidFormat,
    StringDotFormatMissingArgument,
    StringDotFormatMixingAutomatic,
)
from tests.conftest import assert_error, assert_no_errors


class TestStringDotFormatInvalidFormat:
    """Tests for F521: invalid .format() format string."""

    def test_valid_format_ok(self):
        assert_no_errors(
            StringDotFormatInvalidFormat,
            """
s = "{} {}".format(1, 2)
""",
        )

    def test_invalid_format(self):
        assert_error(
            StringDotFormatInvalidFormat,
            """
s = "{".format()
""",
            "F521",
        )

    def test_unknown_conversion(self):
        assert_error(
            StringDotFormatInvalidFormat,
            """
s = "{0!z}".format(1)
""",
            "F521",
        )


class TestStringDotFormatMixingAutomatic:
    """Tests for F525: mixing automatic and manual numbering."""

    def test_all_auto_ok(self):
        assert_no_errors(
            StringDotFormatMixingAutomatic,
            """
s = "{} {}".format(1, 2)
""",
        )

    def test_all_manual_ok(self):
        assert_no_errors(
            StringDotFormatMixingAutomatic,
            """
s = "{0} {1}".format(1, 2)
""",
        )

    def test_mixing_auto_manual(self):
        assert_error(
            StringDotFormatMixingAutomatic,
            """
s = "{} {0}".format(1, 2)
""",
            "F525",
        )


class TestStringDotFormatExtraPositionalArguments:
    """Tests for F523: extra positional arguments."""

    def test_correct_count_ok(self):
        assert_no_errors(
            StringDotFormatExtraPositionalArguments,
            """
s = "{0} {1}".format(1, 2)
""",
        )

    def test_extra_args(self):
        assert_error(
            StringDotFormatExtraPositionalArguments,
            """
s = "{0}".format(1, 2, 3)
""",
            "F523",
        )


class TestStringDotFormatExtraNamedArguments:
    """Tests for F522: extra named arguments."""

    def test_correct_names_ok(self):
        assert_no_errors(
            StringDotFormatExtraNamedArguments,
            """
s = "{name}".format(name=1)
""",
        )

    def test_extra_named_args(self):
        assert_error(
            StringDotFormatExtraNamedArguments,
            """
s = "{name}".format(name=1, other=2)
""",
            "F522",
        )


class TestStringDotFormatMissingArgument:
    """Tests for F524: missing arguments."""

    def test_all_args_present_ok(self):
        assert_no_errors(
            StringDotFormatMissingArgument,
            """
s = "{0} {1}".format(1, 2)
""",
        )

    def test_missing_positional(self):
        assert_error(
            StringDotFormatMissingArgument,
            """
s = "{0} {1}".format(1)
""",
            "F524",
        )

    def test_missing_named(self):
        assert_error(
            StringDotFormatMissingArgument,
            """
s = "{name}".format()
""",
            "F524",
        )


class TestPercentFormatInvalidFormat:
    """Tests for F501: invalid % format string."""

    def test_valid_format_ok(self):
        assert_no_errors(
            PercentFormatInvalidFormat,
            """
s = "%s %d" % ("hello", 42)
""",
        )


class TestPercentFormatExpectedMapping:
    """Tests for F502: expected mapping, got sequence."""

    def test_mapping_with_mapping_ok(self):
        assert_no_errors(
            PercentFormatExpectedMapping,
            """
s = "%(name)s" % {"name": "value"}
""",
        )

    def test_mapping_with_tuple(self):
        assert_error(
            PercentFormatExpectedMapping,
            """
s = "%(name)s" % (1, 2)
""",
            "F502",
        )


class TestPercentFormatExpectedSequence:
    """Tests for F503: expected sequence, got mapping."""

    def test_sequence_with_tuple_ok(self):
        assert_no_errors(
            PercentFormatExpectedSequence,
            """
s = "%s %s" % (1, 2)
""",
        )

    def test_sequence_with_dict(self):
        assert_error(
            PercentFormatExpectedSequence,
            """
s = "%s %s" % {"a": 1}
""",
            "F503",
        )


class TestPercentFormatPositionalCountMismatch:
    """Tests for F507: positional count mismatch."""

    def test_correct_count_ok(self):
        assert_no_errors(
            PercentFormatPositionalCountMismatch,
            """
s = "%s %s" % (1, 2)
""",
        )

    def test_too_few_args(self):
        assert_error(
            PercentFormatPositionalCountMismatch,
            """
s = "%s %s" % (1,)
""",
            "F507",
        )

    def test_too_many_args(self):
        assert_error(
            PercentFormatPositionalCountMismatch,
            """
s = "%s" % (1, 2, 3)
""",
            "F507",
        )

    def test_non_literal_tuple_rhs_no_false_positive(self):
        assert_no_errors(
            PercentFormatPositionalCountMismatch,
            """
data = (1, 2)
s = "%s %s" % data
""",
        )

    def test_star_width_no_false_positive(self):
        assert_no_errors(
            PercentFormatPositionalCountMismatch,
            """
s = "%*d" % (10, 42)
""",
        )


class TestPercentFormatMixedPositionalAndNamed:
    """Tests for F506: mixing positional and named placeholders."""

    def test_all_positional_ok(self):
        assert_no_errors(
            PercentFormatMixedPositionalAndNamed,
            """
s = "%s %s" % (1, 2)
""",
        )

    def test_all_named_ok(self):
        assert_no_errors(
            PercentFormatMixedPositionalAndNamed,
            """
s = "%(a)s %(b)s" % {"a": 1, "b": 2}
""",
        )

    def test_mixed_positional_and_named(self):
        assert_error(
            PercentFormatMixedPositionalAndNamed,
            """
s = "%s %(name)s" % (1, {"name": 2})
""",
            "F506",
        )


class TestPercentFormatUnsupportedCharacter:
    """Tests for F509: unsupported format character."""

    def test_valid_character_ok(self):
        assert_no_errors(
            PercentFormatUnsupportedCharacter,
            """
s = "%s %d %f" % (1, 2, 3.0)
""",
        )

    def test_unsupported_character(self):
        assert_error(
            PercentFormatUnsupportedCharacter,
            """
s = "%z" % 1
""",
            "F509",
        )

    def test_raw_string_unsupported_character(self):
        assert_error(
            PercentFormatUnsupportedCharacter,
            """
s = r"%z" % 1
""",
            "F509",
        )

    def test_triple_quoted_raw_unsupported_character(self):
        assert_error(
            PercentFormatUnsupportedCharacter,
            '''
s = r"""%z""" % 1
''',
            "F509",
        )


class TestPercentFormatExtraNamedArguments:
    """Tests for F504: unused named arguments."""

    def test_all_used_ok(self):
        assert_no_errors(
            PercentFormatExtraNamedArguments,
            """
s = "%(name)s" % {"name": 1}
""",
        )

    def test_unused_named_arg(self):
        assert_error(
            PercentFormatExtraNamedArguments,
            """
s = "%(name)s" % {"name": 1, "other": 2}
""",
            "F504",
        )


class TestPercentFormatMissingArgument:
    """Tests for F505: missing named argument."""

    def test_all_present_ok(self):
        assert_no_errors(
            PercentFormatMissingArgument,
            """
s = "%(a)s %(b)s" % {"a": 1, "b": 2}
""",
        )

    def test_missing_named_arg(self):
        assert_error(
            PercentFormatMissingArgument,
            """
s = "%(a)s %(b)s" % {"a": 1}
""",
            "F505",
        )

    def test_bytes_string_missing_named_arg(self):
        assert_error(
            PercentFormatMissingArgument,
            """
s = b"%(a)s" % {}
""",
            "F505",
        )


class TestPercentFormatStarRequiresSequence:
    """Tests for F508: * width/precision requires sequence."""

    def test_star_with_tuple_ok(self):
        assert_no_errors(
            PercentFormatStarRequiresSequence,
            """
s = "%*s" % (5, "hello")
""",
        )

    def test_star_with_dict(self):
        assert_error(
            PercentFormatStarRequiresSequence,
            """
s = "%*s" % {"width": 5}
""",
            "F508",
        )
