import unittest

from src.core.text_parser import parse_text


class TextParserTest(unittest.TestCase):
    def test_preserves_manual_line_breaks_and_blank_paragraphs(self):
        text = "第一段\n\n第二段\r\n第三段"
        self.assertEqual(
            parse_text(text, 100),
            ["第一段", "", "第二段", "第三段"],
        )

    def test_wraps_each_paragraph_without_merging_them(self):
        text = "abcdef\n中文段落"
        self.assertEqual(
            parse_text(text, 3),
            ["abc", "def", "中", "文", "段", "落"],
        )

    def test_preserves_trailing_blank_line(self):
        self.assertEqual(parse_text("正文\n", 100), ["正文", ""])

    def test_can_restore_original_continuous_layout(self):
        text = "第一段\n\n第二段\r\n第三段"
        self.assertEqual(
            parse_text(text, 100, preserve_line_breaks=False),
            ["第一段第二段第三段"],
        )

    def test_continuous_layout_ignores_newline_only_text(self):
        self.assertEqual(
            parse_text("\n\r\n", 100, preserve_line_breaks=False), [])


if __name__ == "__main__":
    unittest.main()
