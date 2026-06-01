"""Tests for whitespace rules (E2xx)."""

from rude.rules.pycodestyle import (
    BlockCommentShouldStartWithSpace,
    InlineCommentShouldStartWithSpace,
    MissingWhitespaceAfterComma,
    MissingWhitespaceAfterKeyword,
    MissingWhitespaceAroundArithmeticOperator,
    MissingWhitespaceAroundBitwiseOperator,
    MissingWhitespaceAroundModuloOperator,
    # E225-E228
    MissingWhitespaceAroundOperator,
    # E241-E242
    MultipleSpacesAfterComma,
    # E271-E275
    MultipleSpacesAfterKeyword,
    MultipleSpacesAfterOperator,
    MultipleSpacesBeforeKeyword,
    # E221-E224
    MultipleSpacesBeforeOperator,
    TabAfterComma,
    TabAfterKeyword,
    TabAfterOperator,
    TabBeforeKeyword,
    TabBeforeOperator,
    TooManyHashesForBlockComment,
    TwoSpacesBeforeInlineComment,
    UnexpectedSpacesAroundKeywordEquals,
    WhitespaceAfterOpenBracket,
    WhitespaceBeforeCloseBracket,
    WhitespaceBeforeParameters,
)
from tests.conftest import check_source


class TestWhitespaceAfterOpenBracket:
    """Tests for E201: whitespace after '('."""

    def test_space_after_paren(self):
        source = "foo( x)"
        diagnostics = check_source(WhitespaceAfterOpenBracket, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E201"

    def test_no_space_ok(self):
        source = "foo(x)"
        diagnostics = check_source(WhitespaceAfterOpenBracket, source)
        assert len(diagnostics) == 0


class TestWhitespaceBeforeCloseBracket:
    """Tests for E202: whitespace before ')'."""

    def test_space_before_paren(self):
        source = "foo(x )"
        diagnostics = check_source(WhitespaceBeforeCloseBracket, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E202"

    def test_no_space_ok(self):
        source = "foo(x)"
        diagnostics = check_source(WhitespaceBeforeCloseBracket, source)
        assert len(diagnostics) == 0


class TestWhitespaceBeforeParameters:
    """Tests for E211: whitespace before '('."""

    def test_space_before_call(self):
        source = "foo (x)"
        diagnostics = check_source(WhitespaceBeforeParameters, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E211"

    def test_no_space_ok(self):
        source = "foo(x)"
        diagnostics = check_source(WhitespaceBeforeParameters, source)
        assert len(diagnostics) == 0


class TestMissingWhitespaceAfterComma:
    """Tests for E231: missing whitespace after ','."""

    def test_no_space_after_comma(self):
        source = "[1,2,3]"
        diagnostics = check_source(MissingWhitespaceAfterComma, source)
        assert len(diagnostics) == 2  # Two commas without space
        assert all(d.code == "E231" for d in diagnostics)

    def test_space_after_comma_ok(self):
        source = "[1, 2, 3]"
        diagnostics = check_source(MissingWhitespaceAfterComma, source)
        assert len(diagnostics) == 0

    def test_no_space_after_dict_colon(self):
        source = "{1:2}"
        diagnostics = check_source(MissingWhitespaceAfterComma, source)
        assert any(d.code == "E231" for d in diagnostics)

    def test_no_space_after_annotation_colon(self):
        source = "def f(x:int): pass"
        diagnostics = check_source(MissingWhitespaceAfterComma, source)
        assert any(d.code == "E231" for d in diagnostics)


class TestUnexpectedSpacesAroundKeywordEquals:
    """Tests for E251: unexpected spaces around keyword / parameter equals."""

    def test_space_around_default(self):
        source = "def foo(x = 1):\n    pass"
        diagnostics = check_source(UnexpectedSpacesAroundKeywordEquals, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E251"

    def test_no_space_ok(self):
        source = "def foo(x=1):\n    pass"
        diagnostics = check_source(UnexpectedSpacesAroundKeywordEquals, source)
        assert len(diagnostics) == 0


class TestTwoSpacesBeforeInlineComment:
    """Tests for E261: at least two spaces before inline comment."""

    def test_one_space(self):
        source = "x = 1 # comment"
        diagnostics = check_source(TwoSpacesBeforeInlineComment, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E261"

    def test_two_spaces_ok(self):
        source = "x = 1  # comment"
        diagnostics = check_source(TwoSpacesBeforeInlineComment, source)
        assert len(diagnostics) == 0


class TestInlineCommentShouldStartWithSpace:
    """Tests for E262: inline comment should start with '# '."""

    def test_no_space_after_hash(self):
        source = "x = 1  #comment"
        diagnostics = check_source(InlineCommentShouldStartWithSpace, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E262"

    def test_space_after_hash_ok(self):
        source = "x = 1  # comment"
        diagnostics = check_source(InlineCommentShouldStartWithSpace, source)
        assert len(diagnostics) == 0


class TestBlockCommentShouldStartWithSpace:
    """Tests for E265: block comment should start with '# '."""

    def test_no_space_after_hash(self):
        source = "#comment"
        diagnostics = check_source(BlockCommentShouldStartWithSpace, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E265"

    def test_space_after_hash_ok(self):
        source = "# comment"
        diagnostics = check_source(BlockCommentShouldStartWithSpace, source)
        assert len(diagnostics) == 0

    def test_shebang_ok(self):
        source = "#!/usr/bin/env python"
        diagnostics = check_source(BlockCommentShouldStartWithSpace, source)
        assert len(diagnostics) == 0


class TestTooManyHashesForBlockComment:
    """Tests for E266: too many leading '#' for block comment."""

    def test_two_hashes(self):
        source = "## comment"
        diagnostics = check_source(TooManyHashesForBlockComment, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E266"

    def test_one_hash_ok(self):
        source = "# comment"
        diagnostics = check_source(TooManyHashesForBlockComment, source)
        assert len(diagnostics) == 0

    def test_separator_ok(self):
        source = "########"
        diagnostics = check_source(TooManyHashesForBlockComment, source)
        assert len(diagnostics) == 0


# ─────────────────────────────────────────────────────────────────────────────
# E221-E224: Whitespace around operators
# ─────────────────────────────────────────────────────────────────────────────


class TestMultipleSpacesBeforeOperator:
    """Tests for E221: multiple spaces before operator."""

    def test_multiple_spaces_before(self):
        source = "a = 4  + 5"
        diagnostics = check_source(MultipleSpacesBeforeOperator, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E221"

    def test_single_space_ok(self):
        source = "a = 4 + 5"
        diagnostics = check_source(MultipleSpacesBeforeOperator, source)
        assert len(diagnostics) == 0


class TestMultipleSpacesAfterOperator:
    """Tests for E222: multiple spaces after operator."""

    def test_multiple_spaces_after(self):
        source = "a = 4 +  5"
        diagnostics = check_source(MultipleSpacesAfterOperator, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E222"

    def test_single_space_ok(self):
        source = "a = 4 + 5"
        diagnostics = check_source(MultipleSpacesAfterOperator, source)
        assert len(diagnostics) == 0


class TestTabBeforeOperator:
    """Tests for E223: tab before operator."""

    def test_tab_before(self):
        source = "a = 4\t+ 5"
        diagnostics = check_source(TabBeforeOperator, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E223"

    def test_space_ok(self):
        source = "a = 4 + 5"
        diagnostics = check_source(TabBeforeOperator, source)
        assert len(diagnostics) == 0


class TestTabAfterOperator:
    """Tests for E224: tab after operator."""

    def test_tab_after(self):
        source = "a = 4 +\t5"
        diagnostics = check_source(TabAfterOperator, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E224"

    def test_space_ok(self):
        source = "a = 4 + 5"
        diagnostics = check_source(TabAfterOperator, source)
        assert len(diagnostics) == 0


# ─────────────────────────────────────────────────────────────────────────────
# E225-E228: Missing whitespace around operators
# ─────────────────────────────────────────────────────────────────────────────


class TestMissingWhitespaceAroundOperator:
    """Tests for E225: missing whitespace around operator."""

    def test_no_space_around_operator(self):
        source = "i=i+1"
        diagnostics = check_source(MissingWhitespaceAroundOperator, source)
        assert len(diagnostics) >= 1
        assert all(d.code == "E225" for d in diagnostics)

    def test_space_around_operator_ok(self):
        source = "i = i + 1"
        diagnostics = check_source(MissingWhitespaceAroundOperator, source)
        assert len(diagnostics) == 0

    def test_default_parameter_ok(self):
        source = "def foo(x=1):\n    pass"
        diagnostics = check_source(MissingWhitespaceAroundOperator, source)
        assert len(diagnostics) == 0


class TestMissingWhitespaceAroundArithmeticOperator:
    """Tests for E226: missing whitespace around arithmetic operator."""

    def test_no_space_around_arithmetic(self):
        source = "c = a+b"
        diagnostics = check_source(MissingWhitespaceAroundArithmeticOperator, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E226"

    def test_space_around_arithmetic_ok(self):
        source = "c = a + b"
        diagnostics = check_source(MissingWhitespaceAroundArithmeticOperator, source)
        assert len(diagnostics) == 0


class TestMissingWhitespaceAroundBitwiseOperator:
    """Tests for E227: missing whitespace around bitwise operator."""

    def test_no_space_around_bitwise(self):
        source = "x = a|b"
        diagnostics = check_source(MissingWhitespaceAroundBitwiseOperator, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E227"

    def test_space_around_bitwise_ok(self):
        source = "x = a | b"
        diagnostics = check_source(MissingWhitespaceAroundBitwiseOperator, source)
        assert len(diagnostics) == 0


class TestMissingWhitespaceAroundModuloOperator:
    """Tests for E228: missing whitespace around modulo operator."""

    def test_no_space_around_modulo(self):
        source = "x = a%b"
        diagnostics = check_source(MissingWhitespaceAroundModuloOperator, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E228"

    def test_space_around_modulo_ok(self):
        source = "x = a % b"
        diagnostics = check_source(MissingWhitespaceAroundModuloOperator, source)
        assert len(diagnostics) == 0


# ─────────────────────────────────────────────────────────────────────────────
# E241-E242: Multiple spaces/tab after comma
# ─────────────────────────────────────────────────────────────────────────────


class TestMultipleSpacesAfterComma:
    """Tests for E241: multiple spaces after ','."""

    def test_multiple_spaces_after_comma(self):
        source = "a = (1,  2)"
        diagnostics = check_source(MultipleSpacesAfterComma, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E241"

    def test_single_space_ok(self):
        source = "a = (1, 2)"
        diagnostics = check_source(MultipleSpacesAfterComma, source)
        assert len(diagnostics) == 0


class TestTabAfterComma:
    """Tests for E242: tab after ','."""

    def test_tab_after_comma(self):
        source = "a = (1,\t2)"
        diagnostics = check_source(TabAfterComma, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E242"

    def test_space_ok(self):
        source = "a = (1, 2)"
        diagnostics = check_source(TabAfterComma, source)
        assert len(diagnostics) == 0


# ─────────────────────────────────────────────────────────────────────────────
# E271-E275: Whitespace around keywords
# ─────────────────────────────────────────────────────────────────────────────


class TestMultipleSpacesAfterKeyword:
    """Tests for E271: multiple spaces after keyword."""

    def test_multiple_spaces_after_keyword(self):
        source = "if  x:\n    pass"
        diagnostics = check_source(MultipleSpacesAfterKeyword, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E271"

    def test_single_space_ok(self):
        source = "if x:\n    pass"
        diagnostics = check_source(MultipleSpacesAfterKeyword, source)
        assert len(diagnostics) == 0


class TestMultipleSpacesBeforeKeyword:
    """Tests for E272: multiple spaces before keyword."""

    def test_multiple_spaces_before_keyword(self):
        source = "True  and False"
        diagnostics = check_source(MultipleSpacesBeforeKeyword, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E272"

    def test_single_space_ok(self):
        source = "True and False"
        diagnostics = check_source(MultipleSpacesBeforeKeyword, source)
        assert len(diagnostics) == 0


class TestTabAfterKeyword:
    """Tests for E273: tab after keyword."""

    def test_tab_after_keyword(self):
        source = "if\tx:\n    pass"
        diagnostics = check_source(TabAfterKeyword, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E273"

    def test_space_ok(self):
        source = "if x:\n    pass"
        diagnostics = check_source(TabAfterKeyword, source)
        assert len(diagnostics) == 0


class TestTabBeforeKeyword:
    """Tests for E274: tab before keyword."""

    def test_tab_before_keyword(self):
        source = "True\tand False"
        diagnostics = check_source(TabBeforeKeyword, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E274"

    def test_space_ok(self):
        source = "True and False"
        diagnostics = check_source(TabBeforeKeyword, source)
        assert len(diagnostics) == 0


class TestMissingWhitespaceAfterKeyword:
    """Tests for E275: missing whitespace after keyword."""

    def test_no_space_after_keyword(self):
        source = "if(x):\n    pass"
        diagnostics = check_source(MissingWhitespaceAfterKeyword, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E275"

    def test_space_after_keyword_ok(self):
        source = "if (x):\n    pass"
        diagnostics = check_source(MissingWhitespaceAfterKeyword, source)
        assert len(diagnostics) == 0

    def test_keyword_in_string_no_false_positive(self):
        """E275 should not trigger for keywords inside string literals."""
        source = 'x = "if(x)"'
        diagnostics = check_source(MissingWhitespaceAfterKeyword, source)
        assert len(diagnostics) == 0

    def test_keyword_in_fstring_no_false_positive(self):
        """E275 should not trigger for keywords inside f-strings."""
        source = 'x = f"value is {y} if(true)"'
        diagnostics = check_source(MissingWhitespaceAfterKeyword, source)
        assert len(diagnostics) == 0

    def test_keyword_in_comment_no_false_positive(self):
        """E275 should not trigger for keywords inside comments."""
        source = "x = 1  # if(condition) was here"
        diagnostics = check_source(MissingWhitespaceAfterKeyword, source)
        assert len(diagnostics) == 0

    def test_multiple_keywords_without_space(self):
        """E275 detects multiple violations."""
        source = "if(a) and not(b):\n    pass"
        diagnostics = check_source(MissingWhitespaceAfterKeyword, source)
        assert len(diagnostics) == 2
        assert all(d.code == "E275" for d in diagnostics)

    def test_return_without_space(self):
        """E275 detects missing space after return."""
        source = "def f():\n    return(1)"
        diagnostics = check_source(MissingWhitespaceAfterKeyword, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E275"

    def test_assert_without_space(self):
        """E275 detects missing space after assert."""
        source = "assert(x)"
        diagnostics = check_source(MissingWhitespaceAfterKeyword, source)
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "E275"
