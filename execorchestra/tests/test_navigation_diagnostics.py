import json
from pathlib import Path
import tempfile
import uuid
import unittest
from unittest.mock import patch

from scripts.research_browser import inline_anchor_targets, is_access_challenge, page_chunk
from sgar_mvp.src.research_navigation_audit import record_navigation, url_identity


class NavigationDiagnosticsTests(unittest.TestCase):
    def test_http_200_challenge_requires_corroborating_page_content(self):
        body = "Example\nVerifying your browser\nComplete the check below to continue to Example."
        self.assertTrue(is_access_challenge("Verifying your browser | Example", body))
        self.assertFalse(is_access_challenge("Login guide", body))
        self.assertFalse(is_access_challenge("Verifying your browser", "How to confirm your installed version"))
        self.assertFalse(is_access_challenge("Verification report", "An appendix discusses browser checks"))
        for marker in ("Verify you are human", "Checking your browser", "Just a moment..."):
            self.assertTrue(is_access_challenge("Example", marker))

    def test_join_matches_requested_or_redirected_url_without_logging_query_or_snippets(self):
        def observation(tool, number, body, **kw):
            return json.dumps({"session_id":"S", "turn_id":"T", "observation_id":number,
                               "observation_sha256":"0"*64, "resource_id":"tool."+tool+".v1",
                               "status":"success", "public_result":body, **kw})
        source = "https://Sources.example:443/item?token=private-value#ref"
        search = observation("searxng_search", "obs_1", {"result_count":1, "records":[
            {"rank":1, "title":"Report", "url":source, "content":"private snippet"}]})
        read = observation("browser_read_page", "obs_2", {"final_url":"https://mirror.example/a", "title":"Report"})
        directory = Path(tempfile.gettempdir()) / ("navigation-" + uuid.uuid4().hex)
        directory.mkdir()
        self.addCleanup(directory.rmdir)
        trace_path = directory / "research_navigation.jsonl"
        self.addCleanup(trace_path.unlink, missing_ok=True)
        record_navigation(directory, {"query":"raw-search-phrase"}, search)
        record_navigation(directory, {"url":source.split("#")[0]}, read)
        record_navigation(directory, {}, observation("searxng_search","obs_3",{},public_result_complete=False))
        raw = trace_path.read_text(encoding="utf8")
        s, b, partial = map(json.loads, raw.splitlines())
        self.assertEqual(s["candidates"][0]["url"], b["requested"])
        self.assertNotEqual(b["requested"], b["final"])
        self.assertTrue(s["complete_list"])
        self.assertFalse(partial["complete_list"])
        for omitted in ("private-value", "private snippet", "raw-search-phrase"):
            self.assertNotIn(omitted, raw)
        self.assertIsNone(url_identity("https://user:secret@example.org/p"))
        self.assertNotEqual(url_identity("https://x.test/?id=1"), url_identity("https://x.test/?id=2"))

    def test_recorder_failure_does_not_propagate(self):
        with patch("os.open", side_effect=OSError("private path")), self.assertLogs(level="WARNING") as logs:
            record_navigation(Path("."), {}, json.dumps({"resource_id":"tool.browser_read_page.v1",
                "session_id":"S", "turn_id":"T", "observation_id":"obs_1", "status":"failure",
                "observation_sha256":"a"*64}))
        self.assertNotIn("private path", str(logs.output))

    def test_ambiguous_labels_skipped_offsets_still_reconstruct_text(self):
        text = "Reference Reference\n" + "z"*4980 + " Bulletin\n" + "q"*1000
        annotations = [("Reference","https://example.org/a"), ("Bulletin","https://example.org/b")]
        annotated = inline_anchor_targets(text, annotations)
        self.assertEqual(annotated, text.replace("Bulletin","Bulletin (https://example.org/b)"))
        page = {"text":annotated, "links":[{"text":"Reference","url":"https://example.org/a"}], "page_id":"fixture"}
        a = page_chunk(page)
        b = page_chunk(page, a["next_text_offset"])
        self.assertEqual(a["text"] + b["text"], annotated)
        self.assertEqual(a["links"], page["links"])
        long_text = "T"*249999 + "X"
        self.assertEqual(inline_anchor_targets(long_text,[("X","https://x.org/")]), long_text)
