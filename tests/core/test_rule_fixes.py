"""Tests for individual rule autofixes."""

from __future__ import annotations

from tests.conftest import assert_fix


class TestWhitespaceFixes:
    def test_e221_multiple_spaces_before_operator(self):
        from rude.rules.pycodestyle.whitespace import MultipleSpacesBeforeOperator

        assert_fix(MultipleSpacesBeforeOperator, "a = 4  + 5\n", "a = 4 + 5\n")

    def test_e222_multiple_spaces_after_operator(self):
        from rude.rules.pycodestyle.whitespace import MultipleSpacesAfterOperator

        assert_fix(MultipleSpacesAfterOperator, "a = 4 +  5\n", "a = 4 + 5\n")

    def test_e223_tab_before_operator(self):
        from rude.rules.pycodestyle.whitespace import TabBeforeOperator

        assert_fix(TabBeforeOperator, "a = 4\t+ 5\n", "a = 4 + 5\n")

    def test_e224_tab_after_operator(self):
        from rude.rules.pycodestyle.whitespace import TabAfterOperator

        assert_fix(TabAfterOperator, "a = 4 +\t5\n", "a = 4 + 5\n")

    def test_e241_multiple_spaces_after_comma(self):
        from rude.rules.pycodestyle.whitespace import MultipleSpacesAfterComma

        assert_fix(MultipleSpacesAfterComma, "a = (1,  2)\n", "a = (1, 2)\n")

    def test_e242_tab_after_comma(self):
        from rude.rules.pycodestyle.whitespace import TabAfterComma

        assert_fix(TabAfterComma, "a = (1,\t2)\n", "a = (1, 2)\n")

    def test_e261_one_space_before_inline_comment(self):
        from rude.rules.pycodestyle.whitespace import TwoSpacesBeforeInlineComment

        assert_fix(TwoSpacesBeforeInlineComment, "x = 1 # comment\n", "x = 1  # comment\n")

    def test_e262_no_space_after_hash(self):
        from rude.rules.pycodestyle.whitespace import InlineCommentShouldStartWithSpace

        assert_fix(InlineCommentShouldStartWithSpace, "x = 1  #comment\n", "x = 1  # comment\n")

    def test_e265_block_comment_no_space(self):
        from rude.rules.pycodestyle.whitespace import BlockCommentShouldStartWithSpace

        assert_fix(BlockCommentShouldStartWithSpace, "#comment\n", "# comment\n")

    def test_e266_double_hash(self):
        from rude.rules.pycodestyle.whitespace import TooManyHashesForBlockComment

        assert_fix(TooManyHashesForBlockComment, "##comment\n", "# comment\n")

    def test_e271_multiple_spaces_after_keyword(self):
        from rude.rules.pycodestyle.whitespace import MultipleSpacesAfterKeyword

        assert_fix(MultipleSpacesAfterKeyword, "import  os\n", "import os\n")

    def test_e272_multiple_spaces_before_keyword(self):
        from rude.rules.pycodestyle.whitespace import MultipleSpacesBeforeKeyword

        assert_fix(MultipleSpacesBeforeKeyword, "True  and False\n", "True and False\n")

    def test_e273_tab_after_keyword(self):
        from rude.rules.pycodestyle.whitespace import TabAfterKeyword

        assert_fix(TabAfterKeyword, "import\tos\n", "import os\n")

    def test_e274_tab_before_keyword(self):
        from rude.rules.pycodestyle.whitespace import TabBeforeKeyword

        assert_fix(TabBeforeKeyword, "True\tand False\n", "True and False\n")

    def test_e275_missing_space_after_keyword(self):
        from rude.rules.pycodestyle.whitespace import MissingWhitespaceAfterKeyword

        assert_fix(MissingWhitespaceAfterKeyword, "if(x):\n    pass\n", "if (x):\n    pass\n")


class TestStatementFixes:
    def test_e703_trailing_semicolon(self):
        from rude.rules.pycodestyle.statements import StatementEndsWithSemicolon

        assert_fix(StatementEndsWithSemicolon, "x = 1;\n", "x = 1\n")

    def test_e722_bare_except(self):
        from rude.rules.pycodestyle.statements import BareExcept

        assert_fix(
            BareExcept,
            "try:\n    pass\nexcept:\n    pass\n",
            "try:\n    pass\nexcept Exception:\n    pass\n",
        )


class TestSyntaxFixes:
    def test_f632_is_literal(self):
        from rude.rules.pyflakes.syntax import IsLiteral

        assert_fix(IsLiteral, "x is 1\n", "x == 1\n")

    def test_f632_is_not_literal(self):
        from rude.rules.pyflakes.syntax import IsLiteral

        assert_fix(IsLiteral, "x is not 1\n", "x != 1\n")
