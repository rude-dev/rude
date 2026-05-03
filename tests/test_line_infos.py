"""Tests for extended line_infos metadata from Rust."""

from rude._rust import LineInfo, analyze_source


def get_line_infos(source: str) -> list[LineInfo]:
    model = analyze_source(source.encode())
    return model.line_infos


class TestCommentMetadata:
    def test_inline_comment_two_spaces(self):
        infos = get_line_infos("x = 1  # hello\n")
        info = infos[0]
        assert info.spaces_before_comment == 2
        assert info.char_after_hash == ord(" ")
        assert info.leading_hashes == 1

    def test_inline_comment_one_space(self):
        infos = get_line_infos("x = 1 # hello\n")
        assert infos[0].spaces_before_comment == 1

    def test_block_comment(self):
        infos = get_line_infos("# block comment\n")
        info = infos[0]
        assert info.spaces_before_comment == -1  # not inline
        assert info.char_after_hash == ord(" ")
        assert info.leading_hashes == 1

    def test_double_hash(self):
        infos = get_line_infos("## section\n")
        assert infos[0].leading_hashes == 2

    def test_no_space_after_hash(self):
        infos = get_line_infos("#comment\n")
        assert infos[0].char_after_hash == ord("c")

    def test_no_comment(self):
        infos = get_line_infos("x = 1\n")
        info = infos[0]
        assert info.spaces_before_comment == -1
        assert info.char_after_hash == 0
        assert info.leading_hashes == 0

    def test_empty_comment(self):
        infos = get_line_infos("#\n")
        info = infos[0]
        assert info.char_after_hash == 0
        assert info.leading_hashes == 1

    def test_indented_block_comment(self):
        infos = get_line_infos("    # indented\n")
        info = infos[0]
        assert info.spaces_before_comment == -1  # block comment (only whitespace before #)
        assert info.char_after_hash == ord(" ")

    def test_inline_no_space_before_hash(self):
        infos = get_line_infos("x = 1# bad\n")
        info = infos[0]
        assert info.spaces_before_comment == 0  # zero spaces before comment
