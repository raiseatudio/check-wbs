import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_wbs import read_limited


DOCX_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Người chơi mở ô.</w:t></w:r></w:p>
    <w:p><w:r><w:t>Có nút cash out.</w:t></w:r></w:p>
  </w:body>
</w:document>
"""


class ReadTextTest(unittest.TestCase):
    def test_docx_paragraphs_become_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gdd.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", DOCX_XML)
            text, line_count, truncated = read_limited(path)
        self.assertEqual(text, "Người chơi mở ô.\nCó nút cash out.")
        self.assertEqual(line_count, 2)
        self.assertFalse(truncated)

    def test_rtf_controls_are_stripped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gdd.rtf"
            path.write_text(r"{\rtf1\ansi Hello\par World}", encoding="utf-8")
            text, line_count, truncated = read_limited(path)
        self.assertEqual(text, "Hello\nWorld")
        self.assertEqual(line_count, 2)
        self.assertFalse(truncated)

    def test_plain_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gdd.txt"
            path.write_text("Dòng 1\nDòng 2\n", encoding="utf-8")
            text, line_count, truncated = read_limited(path)
        self.assertEqual(text, "Dòng 1\nDòng 2\n")
        self.assertEqual(line_count, 2)
        self.assertFalse(truncated)


if __name__ == "__main__":
    unittest.main()
