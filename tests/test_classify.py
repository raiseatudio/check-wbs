import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_wbs import classify_path


class ClassifyPathTest(unittest.TestCase):
    def test_folder_and_filename_tokens(self):
        cases = {
            "wbs/foo.csv": "wbs",
            "gdd/bar.tsv": "gdd",
            "WBS_export.csv": "wbs",
            "my-wbs.tsv": "wbs",
            "nested/gdd/design.csv": "gdd",
            "GDD-final.csv": "gdd",
            "WBS/Data.CSV": "wbs",
            "exports/my-gdd.csv": "gdd",
            "the-gdd-v2.csv": "gdd",
            "WBS Export.csv": "wbs",
            "wbs\\foo.csv": "wbs",
            "wbs-gdd.csv": "ambiguous",
            "wbs/gdd_export.csv": "ambiguous",
            "gdd/WBS_tasks.csv": "ambiguous",
            "gdd/WBS_tasks.xlsx": "ambiguous",
            "wbs/file.xlsx": "unsupported",
            "WBS.ods": "unsupported",
            "notes.csv": None,
            "mywbs.csv": None,
            "gddv2.csv": None,
            "sheet.xlsm": None,
            "my-wbs/file.csv": None,
            "wbs/readme.md": None,
            "docs/readme.md": None,
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(classify_path(path), expected)


if __name__ == "__main__":
    unittest.main()
