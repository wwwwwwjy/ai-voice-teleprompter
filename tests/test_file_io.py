import tempfile
import unittest
from pathlib import Path

from utils.file_io import IMPORTABLE_SUFFIXES, read_importable_document, write_text_file


class FileIoTest(unittest.TestCase):
    def test_reads_txt_document_with_original_line_breaks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "稿件.txt"
            write_text_file(str(path), "第一段\n\n第二段")
            self.assertEqual(read_importable_document(str(path)), "第一段\n\n第二段")

    def test_supported_import_formats_include_word(self):
        self.assertTrue({".txt", ".doc", ".docx"}.issubset(IMPORTABLE_SUFFIXES))
