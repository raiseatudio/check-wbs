import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check_wbs
from check_wbs import GeminiHTTPError, discord_chunks, is_discord_webhook, read_limited, review_with_gemini


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


class DiscordReportTest(unittest.TestCase):
    def test_webhook_url_shape(self):
        self.assertTrue(
            is_discord_webhook("https://discord.com/api/webhooks/123/token")
        )
        self.assertTrue(
            is_discord_webhook("https://discordapp.com/api/webhooks/123/token")
        )
        self.assertFalse(is_discord_webhook("https://example.com/hook"))
        self.assertFalse(is_discord_webhook("http://discord.com/api/webhooks/123/token"))

    def test_long_report_is_split(self):
        text = "\n".join(f"dong {index}" for index in range(800))
        chunks = discord_chunks(text)
        self.assertGreater(len(chunks), 1)
        self.assertLessEqual(len(chunks), 8)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 2000)
        self.assertTrue(chunks[0].startswith("(1/"))


class GeminiModelOrderTest(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("GEMINI_MODEL", None)

    def test_falls_through_high_demand(self):
        calls = []
        original = check_wbs.call_gemini

        def fake_call(api_key, model, prompt):
            calls.append(model)
            if model != "gemini-2.5-flash":
                raise GeminiHTTPError(503, "high demand", True)
            return "báo cáo"

        check_wbs.call_gemini = fake_call
        try:
            text = review_with_gemini("key", "prompt")
        finally:
            check_wbs.call_gemini = original
        self.assertEqual(
            calls,
            [
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
                "gemini-2.5-flash",
            ],
        )
        self.assertIn("Đã dùng Gemini `gemini-2.5-flash`", text)
        self.assertIn("báo cáo", text)


if __name__ == "__main__":
    unittest.main()
