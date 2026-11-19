import json
import os
import unittest
import urllib.parse
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check_wbs
from check_wbs import (
    EMPTY_INVENTORY,
    Inventory,
    compose_report,
    fetch_sheet_docs,
    find_game_id,
    inventory_game_id,
    oauth_refresh_form,
    parse_commit_message,
    parse_sheet_url,
    rows_to_csv,
)


WBS_URL = "https://docs.google.com/spreadsheets/d/abcDEF_123/edit#gid=15"
GDD_URL = "https://docs.google.com/spreadsheets/d/gddSheet_9/edit?gid=7#gid=3"
DOC_URL = (
    "https://docs.google.com/document/d/12onLlQLkP4CfhsR0j8nmECYek79x9RWk_9t4blx33sQ"
    "/edit?tab=t.0#heading=h.n9zxywuies4v"
)


class CommitParserTest(unittest.TestCase):
    def test_check_wbs_reads_two_labeled_urls_and_hash_gid(self):
        message = f"[check-wbs] wbs: {WBS_URL}\ngdd: {GDD_URL}"
        request = parse_commit_message(message)
        self.assertTrue(request.wbs)
        self.assertFalse(request.files)
        self.assertFalse(request.gdd)
        self.assertEqual(request.wbs_link.spreadsheet_id, "abcDEF_123")
        self.assertEqual(request.wbs_link.gid, "15")
        self.assertEqual(request.wbs_gdd_link.gid, "3")
        self.assertEqual(request.wbs_error, "")

    def test_bare_check_does_not_match_check_wbs(self):
        request = parse_commit_message(f"[check-wbs] wbs: {WBS_URL} gdd: {GDD_URL}")
        self.assertFalse(request.files)
        self.assertTrue(request.wbs)

    def test_bare_check_still_selects_files(self):
        request = parse_commit_message("[check] cập nhật csv")
        self.assertTrue(request.files)
        self.assertFalse(request.wbs)
        self.assertFalse(request.gdd)

    def test_check_gdd_needs_one_gdd_url(self):
        request = parse_commit_message(f"[check-gdd] gdd={GDD_URL}")
        self.assertTrue(request.gdd)
        self.assertEqual(request.gdd_link.spreadsheet_id, "gddSheet_9")
        self.assertEqual(request.gdd_link.gid, "3")
        self.assertEqual(request.gdd_error, "")

    def test_missing_label_is_an_error(self):
        request = parse_commit_message(f"[check-wbs] {WBS_URL}")
        self.assertTrue(request.wbs)
        self.assertIsNone(request.wbs_link)
        self.assertIn("wbs:", request.wbs_error)
        gdd = parse_commit_message("[check-gdd] xem sheet")
        self.assertTrue(gdd.gdd)
        self.assertIn("gdd:", gdd.gdd_error)

    def test_both_commands_in_one_commit(self):
        message = (
            f"[check-wbs] wbs: {WBS_URL} gdd: {GDD_URL}\n"
            f"[check-gdd] gdd: {WBS_URL}"
        )
        request = parse_commit_message(message)
        self.assertTrue(request.wbs)
        self.assertTrue(request.gdd)
        self.assertEqual(request.wbs_link.spreadsheet_id, "abcDEF_123")
        self.assertEqual(request.gdd_link.spreadsheet_id, "abcDEF_123")
        self.assertEqual(request.gdd_link.gid, "15")

    def test_gdd_can_be_a_google_doc(self):
        request = parse_commit_message(f"[check-wbs] wbs: {WBS_URL} gdd: {DOC_URL}")
        self.assertEqual(request.wbs_error, "")
        self.assertEqual(request.wbs_link.kind, "sheet")
        self.assertEqual(request.wbs_gdd_link.kind, "doc")
        self.assertEqual(
            request.wbs_gdd_link.spreadsheet_id,
            "12onLlQLkP4CfhsR0j8nmECYek79x9RWk_9t4blx33sQ",
        )
        self.assertEqual(request.wbs_gdd_link.tab, "t.0")
        gdd_only = parse_commit_message(f"[check-gdd] gdd: {DOC_URL}")
        self.assertEqual(gdd_only.gdd_error, "")
        self.assertEqual(gdd_only.gdd_link.kind, "doc")

    def test_wbs_url_must_stay_a_sheet(self):
        request = parse_commit_message(f"[check-wbs] wbs: {DOC_URL} gdd: {GDD_URL}")
        self.assertIn("Google Sheet", request.wbs_error)
        self.assertIsNone(request.wbs_link)

    def test_query_gid_when_hash_is_absent(self):
        link = parse_sheet_url("https://docs.google.com/spreadsheets/d/abcDEF_123/edit?gid=7")
        self.assertEqual(link.gid, "7")
        self.assertIsNone(parse_sheet_url("https://docs.google.com/spreadsheets/d/abcDEF_123/edit").gid)


class SheetCsvTest(unittest.TestCase):
    def test_rows_quote_commas_and_pad_cells(self):
        text = rows_to_csv([["Cột", "Nội dung"], ["1", "Làm, UI"]])
        self.assertEqual(text, 'Cột,Nội dung\n1,"Làm, UI"\n')

    def test_fetch_keeps_the_gid_tab(self):
        link = parse_sheet_url("https://docs.google.com/spreadsheets/d/sheetId123/edit#gid=9")
        seen = []

        class FakeBody:
            def __init__(self, payload):
                self.payload = payload

            def read(self):
                return json.dumps(self.payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

        def fake_urlopen(request, timeout=60):
            seen.append(request.full_url)
            self.assertNotIn("refresh-token", request.full_url)
            self.assertNotIn("access-token", request.full_url)
            if "/values/" in request.full_url:
                self.assertIn("GDD", urllib.parse.unquote(request.full_url))
                return FakeBody({"values": [["Cột", "Nội dung"], ["1", "Làm, UI"]]})
            return FakeBody(
                {
                    "sheets": [
                        {"properties": {"sheetId": 0, "title": "WBS"}},
                        {"properties": {"sheetId": 9, "title": "GDD"}},
                    ]
                }
            )

        original = check_wbs.urllib.request.urlopen
        check_wbs.urllib.request.urlopen = fake_urlopen
        try:
            bundle = fetch_sheet_docs("access-token", link, "gdd")
        finally:
            check_wbs.urllib.request.urlopen = original
        self.assertEqual(len(bundle.docs), 1)
        self.assertEqual(bundle.docs[0].name, "GDD")
        self.assertIn('"Làm, UI"', bundle.docs[0].text)
        self.assertEqual(len(seen), 2)

    def test_fetch_google_doc_keeps_named_tab(self):
        link = parse_commit_message(f"[check-gdd] gdd: {DOC_URL}").gdd_link

        class FakeBody:
            def __init__(self, payload):
                self.payload = payload

            def read(self):
                return json.dumps(self.payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

        def fake_urlopen(request, timeout=60):
            self.assertIn("includeTabsContent=true", request.full_url)
            self.assertIn("12onLlQLkP4CfhsR0j8nmECYek79x9RWk_9t4blx33sQ", request.full_url)
            return FakeBody(
                {
                    "title": "[gsc00002 - FODB] GDD",
                    "tabs": [
                        {
                            "tabProperties": {"tabId": "t.0", "title": "Luật chơi"},
                            "documentTab": {
                                "body": {
                                    "content": [
                                        {
                                            "paragraph": {
                                                "elements": [
                                                    {"textRun": {"content": "Người chơi mở ô.\n"}}
                                                ]
                                            }
                                        }
                                    ]
                                }
                            },
                        },
                        {
                            "tabProperties": {"tabId": "t.1", "title": "Khác"},
                            "documentTab": {
                                "body": {
                                    "content": [
                                        {
                                            "paragraph": {
                                                "elements": [{"textRun": {"content": "Bỏ tab này.\n"}}]
                                            }
                                        }
                                    ]
                                }
                            },
                        },
                    ],
                }
            )

        original = check_wbs.urllib.request.urlopen
        check_wbs.urllib.request.urlopen = fake_urlopen
        try:
            bundle = fetch_sheet_docs("access-token", link, "gdd")
        finally:
            check_wbs.urllib.request.urlopen = original
        self.assertEqual(bundle.spreadsheet_title, "[gsc00002 - FODB] GDD")
        self.assertEqual(len(bundle.docs), 1)
        self.assertEqual(bundle.docs[0].text, "Người chơi mở ô.\n")
        self.assertEqual(find_game_id(bundle.spreadsheet_title), "gsc00002")


class TokenReportTest(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("GOOGLE_OAUTH_REFRESH_TOKEN", None)
        os.environ.pop("GITHUB_REPOSITORY", None)
        os.environ.pop("GITHUB_RUN_ID", None)
        os.environ.pop("GITHUB_SERVER_URL", None)
        os.environ.pop("PR_NUMBER", None)

    def test_refresh_form_has_no_sheet_url(self):
        form = oauth_refresh_form("client", "secret", "refresh-token-value")
        decoded = urllib.parse.unquote(form)
        self.assertIn("grant_type=refresh_token", form)
        self.assertIn("refresh-token-value", decoded)
        self.assertNotIn("docs.google.com", form)
        self.assertNotIn("docs.google.com", decoded)

    def test_report_lists_sheet_url_and_hides_refresh_token(self):
        os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"] = "super-secret-refresh"
        os.environ["GITHUB_REPOSITORY"] = "acme/check"
        os.environ["GITHUB_SERVER_URL"] = "https://github.com"
        os.environ["GITHUB_RUN_ID"] = "99"
        text = compose_report(
            "Kết luận\nCần chỉnh.",
            Path("."),
            EMPTY_INVENTORY,
            title="Check GDD",
            game_id="gsc00002",
        )
        self.assertTrue(text.startswith("[Check GDD - gsc00002]\n\nKết luận"))
        self.assertNotIn("Lần chạy:", text)
        self.assertNotIn("super-secret-refresh", text)


class GameIdTest(unittest.TestCase):
    def test_game_id_comes_from_file_bracket(self):
        inventory = Inventory(
            wbs=[Path("WBS/[gsc00002 - FODB] WBS_FE - WBS.csv")],
            gdd=[],
            ambiguous=[],
            unsupported=[],
        )
        os.environ["COMMIT_MESSAGE"] = "[check]"
        try:
            self.assertEqual(inventory_game_id(inventory), "gsc00002")
        finally:
            os.environ.pop("COMMIT_MESSAGE", None)

    def test_explicit_game_label_wins(self):
        self.assertEqual(
            find_game_id("[check-wbs] game: FODB", "[gsc00002 - FODB] WBS"),
            "FODB",
        )

    def test_check_marker_is_not_a_game_id(self):
        self.assertEqual(find_game_id("[check-wbs] wbs: https://docs.google.com"), "")


if __name__ == "__main__":
    unittest.main()
