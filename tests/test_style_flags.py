"""Tests for style_flags in line_infos."""

from rude._rust import analyze_source

DOUBLE_SPACE_AROUND_OP = 0x01
TAB_AROUND_OP = 0x02
DOUBLE_SPACE_AFTER_COMMA = 0x04
TAB_AFTER_COMMA = 0x08
DOUBLE_SPACE_AROUND_KW = 0x10
TAB_AROUND_KW = 0x20


def get_flags(source: str) -> list[int]:
    model = analyze_source(source.encode())
    return [info.style_flags for info in model.line_infos]


class TestOperatorFlags:
    def test_double_space_before_op(self):
        flags = get_flags("a  = 1\n")
        assert flags[0] & DOUBLE_SPACE_AROUND_OP

    def test_double_space_after_op(self):
        flags = get_flags("a =  1\n")
        assert flags[0] & DOUBLE_SPACE_AROUND_OP

    def test_tab_before_op(self):
        flags = get_flags("a\t= 1\n")
        assert flags[0] & TAB_AROUND_OP

    def test_tab_after_op(self):
        flags = get_flags("a =\t1\n")
        assert flags[0] & TAB_AROUND_OP

    def test_clean_op(self):
        flags = get_flags("a = 1\n")
        assert not (flags[0] & DOUBLE_SPACE_AROUND_OP)
        assert not (flags[0] & TAB_AROUND_OP)


class TestCommaFlags:
    def test_double_space_after_comma(self):
        flags = get_flags("a = (1,  2)\n")
        assert flags[0] & DOUBLE_SPACE_AFTER_COMMA

    def test_tab_after_comma(self):
        flags = get_flags("a = (1,\t2)\n")
        assert flags[0] & TAB_AFTER_COMMA

    def test_clean_comma(self):
        flags = get_flags("a = (1, 2)\n")
        assert not (flags[0] & DOUBLE_SPACE_AFTER_COMMA)
        assert not (flags[0] & TAB_AFTER_COMMA)


class TestKeywordFlags:
    def test_double_space_after_keyword(self):
        flags = get_flags("if  x:\n")
        assert flags[0] & DOUBLE_SPACE_AROUND_KW

    def test_tab_after_keyword(self):
        flags = get_flags("if\tx:\n")
        assert flags[0] & TAB_AROUND_KW

    def test_clean_keyword(self):
        flags = get_flags("if x:\n")
        assert not (flags[0] & DOUBLE_SPACE_AROUND_KW)
        assert not (flags[0] & TAB_AROUND_KW)

    def test_keyword_in_string_ignored(self):
        flags = get_flags('x = "if  True"\n')
        assert not (flags[0] & DOUBLE_SPACE_AROUND_KW)


class TestNoFalseNegatives:
    """These MUST set the flag (no false negatives allowed)."""

    def test_e271_return_double_space(self):
        flags = get_flags("return  x\n")
        assert flags[0] & DOUBLE_SPACE_AROUND_KW

    def test_e272_double_space_before_and(self):
        flags = get_flags("True  and False\n")
        assert flags[0] & DOUBLE_SPACE_AROUND_KW

    def test_semicolon(self):
        flags = get_flags("a = 1;  b = 2\n")
        assert flags[0] & DOUBLE_SPACE_AFTER_COMMA
