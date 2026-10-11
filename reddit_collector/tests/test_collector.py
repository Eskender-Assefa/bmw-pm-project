"""Offline integrity/recovery tests. All comment fixtures are synthetic."""
import contextlib
import csv
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import httpx
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import collect_reddit as collector

URL = "https://www.reddit.com/r/BMW/comments/abc123/test_thread/"
THREAD = {"id": "abc123", "url": URL, "batches": 0, "stalled_batches": 0}


def raw_comment(index=1, text=None):
    return {"comment_text": text if text is not None else f"Synthetic BMW G60 comment number {index}.",
            "author": "synthetic_test_user", "date_displayed": "2 years ago",
            "source_url": URL, "is_complete": True, "relevant": True}


def extraction_text(comments=None):
    return json.dumps({"access": "readable", "thread_title": "Synthetic G60 discussion",
                       "comments": [raw_comment()] if comments is None else comments}, ensure_ascii=False)


def response_data(text="", source_url=URL, status="completed"):
    output = []
    if source_url:
        output.append({"id": "ws_fixture", "type": "web_search_call", "status": "completed",
                       "action": {"type": "search", "sources": [{"type": "url", "url": source_url}]}})
    output.append({"id": "msg_fixture", "type": "message", "role": "assistant", "status": "completed",
                   "content": [{"type": "output_text", "text": text, "annotations": []}]})
    return {"id": "resp_fixture", "object": "response", "created_at": 0, "status": status,
            "model": "gpt-5.5", "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
            "output": output}


def fixture(index, text=None, thread_id="abc123"):
    body = raw_comment(index, text)["comment_text"]
    digest = collector.text_hash(body)
    source = URL.replace("abc123", thread_id)
    return {"row_id": "web_" + digest, "comment_text": body, "author": "synthetic_test_user",
            "date_displayed": "2 years ago", "thread_id": thread_id,
            "thread_title": "Synthetic BMW G60 test thread", "thread_url": source, "source_url": source,
            "subreddit": "BMW", "retrieved_at_utc": "2026-10-11T00:00:00+00:00", "text_sha256": digest,
            "extraction_method": "openai_web_search_quote_extraction", "text_verification": "unverified_model_extraction",
            "extraction_model": "test-model", "source_response_id": "resp_fixture",
            "source_response_file": "api_responses/000001_extraction.json"}


def batch(rows):
    return collector.ExtractionBatch(rows, "resp_fixture", "api_responses/fixture.json", {})


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        defaults = collector.parse_args([])
        self.config = {"schema_version": collector.SCHEMA_VERSION, "topic": defaults.topic,
                       "scope": defaults.scope, "min_words": defaults.min_words, "subreddits": []}
        self.state = collector.State(self.folder, self.config)

    def tearDown(self):
        self.state.db.close()
        self.temp.cleanup()

    def client(self, handler):
        client = OpenAI(api_key="synthetic-test-key", max_retries=0,
                        http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        self.addCleanup(client.close)
        return client

    def test_thread_url_validation_and_subreddit_filter(self):
        self.assertEqual(collector.reddit_thread(URL)[0], "abc123")
        for url in ["https://reddit.com.evil.test/r/BMW/comments/abc123/",
                    "https://reddit.com@evil.test/r/BMW/comments/abc123/",
                    "https://evil.test/r/BMW/comments/abc123/", "file:///r/BMW/comments/abc123/",
                    "https://www.reddit.com/r/BMW/", "https://[", None]:
            self.assertIsNone(collector.reddit_thread(url))
        self.assertEqual(self.state.add_threads([URL, URL + "c1/", URL.replace("/BMW/", "/cars/")], ["BMW"]), 1)

    def test_discovery_ignores_plain_model_urls(self):
        data = response_data("Use https://www.reddit.com/r/BMW/comments/invented/")
        self.assertEqual(collector.discovery_sources(data), [URL])
        data["output"][0]["status"] = "failed"
        self.assertEqual(collector.discovery_sources(data), [])

    def test_extraction_preserves_quote_but_marks_it_unverified(self):
        body = 'BMW G60 "quoted"\nwith Unicode: gem\u00fctlich \U0001f697'
        record = dict(raw_comment(text=body), author=None, date_displayed=None, comment_id="invented_id",
                      source_url=URL + "invented_comment_id/")
        result = collector.parse_extraction("```json\n" + extraction_text([record]) + "\n``` citation",
                                            response_data(), THREAD, "test-model", "response.json", 30)
        saved = result.rows[0]
        self.assertEqual(saved["comment_text"], body)
        self.assertEqual(saved["text_verification"], "unverified_model_extraction")
        self.assertEqual(saved["source_url"], URL)
        self.assertEqual(saved["row_id"], "web_" + collector.text_hash(body))
        self.assertNotIn("comment_id", saved)
        self.assertIsNone(saved["author"])
        self.assertIsNone(saved["date_displayed"])

    def test_extraction_requires_matching_tool_source_and_web_call(self):
        for data in [response_data(source_url=None), response_data(source_url=URL.replace("abc123", "wrong"))]:
            with self.subTest(data=data), self.assertRaises(collector.ThreadUnavailable):
                collector.parse_extraction(extraction_text(), data, THREAD, "test", "response.json", 30)
        data = response_data(source_url=None)
        data["output"][0]["content"][0]["annotations"] = [{"type": "url_citation", "url": URL}]
        with self.assertRaisesRegex(collector.ThreadUnavailable, "No completed"):
            collector.parse_extraction(extraction_text(), data, THREAD, "test", "response.json", 30)

    def test_malformed_unavailable_and_oversized_extractions_rejected(self):
        outputs = ["not JSON", '{"access":"readable","comments":[',
                   json.dumps({"access": [], "comments": [], "thread_title": "x"}),
                   json.dumps({"access": "unavailable", "comments": [], "thread_title": ""}),
                   extraction_text([raw_comment(1), raw_comment(2)])]
        for output in outputs:
            with self.subTest(output=output), self.assertRaises(collector.ThreadUnavailable):
                collector.parse_extraction(output, response_data(), THREAD, "test", "response.json", 1)
        self.assertEqual(self.state.accepted_count(), 0)

    def test_invalid_individual_records_are_counted_and_excluded(self):
        wrong_source = dict(raw_comment(2), source_url=URL.replace("abc123", "wrong"))
        incomplete = dict(raw_comment(3), is_complete=False)
        irrelevant = dict(raw_comment(4), relevant=False)
        markup = raw_comment(5, "BMW G60 text \ue200cite\ue201bad\ue202")
        result = collector.parse_extraction(extraction_text([raw_comment(), wrong_source, incomplete, irrelevant, markup]),
                                            response_data(), THREAD, "test", "response.json", 30)
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(sum(result.rejected.values()), 4)
        with self.assertRaisesRegex(collector.ThreadUnavailable, "All extracted records"):
            collector.parse_extraction(extraction_text([wrong_source]), response_data(), THREAD, "test", "response.json", 30)

    def test_deduplication_short_deleted_and_bot_comments(self):
        rows = [fixture(1), fixture(1), fixture(2, fixture(1)["comment_text"].upper()),
                fixture(3, "[removed]"), fixture(4, "[deleted]"), fixture(5, "Too short")]
        self.assertEqual(self.state.add_comments(rows + [dict(fixture(6), author="AutoModerator")], 3), 1)
        self.assertEqual(self.state.accepted_count(), 1)

    def test_export_preserves_model_text_and_marks_provenance(self):
        original = '=SUM(1,2)\nBMW G60 "quoted", gem\u00fctlich \U0001f697 <script>alert(1)</script>'
        self.state.add_comments([fixture(1, original), fixture(2)], 3)
        report = collector.export(self.state, 1, "test")
        saved = json.loads((self.folder / "comments.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(saved["comment_text"], original)
        self.assertEqual(saved["text_verification"], "unverified_model_extraction")
        with (self.folder / "comments.csv").open(encoding="utf-8-sig", newline="") as stream:
            self.assertEqual(next(csv.DictReader(stream))["comment_text"], "'" + original)
        markdown = (self.folder / "comments.md").read_text(encoding="utf-8")
        self.assertIn("[Reddit source thread](https://www.reddit.com/r/BMW/comments/abc123/)", markdown)
        self.assertIn("not independently verified", markdown)
        self.assertNotIn("<script>", markdown)
        self.assertEqual(report["status"], "target_reached")
        self.assertEqual(report["accepted_in_checkpoint"], 2)

    def test_full_2000_export_and_resume_without_network(self):
        self.state.add_threads([URL.replace("abc123", f"thread{i}") for i in range(10)])
        args = collector.parse_args(["--count", "2000", "--batch-size", "50"])
        ai, visited = Mock(), []
        def extract(topic, scope, thread, limit, seen):
            start = len(visited) * limit
            visited.append(thread["id"])
            return batch([fixture(i, thread_id=thread["id"]) for i in range(start, start + limit)])
        ai.extract.side_effect = extract
        with contextlib.redirect_stdout(io.StringIO()):
            reason = collector.collect(self.state, args, ai)
        report = collector.export(self.state, 2000, reason)
        rows = [json.loads(line) for line in (self.folder / "comments.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(report["status"], "target_reached")
        self.assertEqual(len(rows), 2000)
        self.assertEqual(len({r["row_id"] for r in rows}), 2000)
        self.assertEqual(len({r["text_sha256"] for r in rows}), 2000)
        self.assertEqual(len(set(visited[:10])), 10)
        self.assertEqual(ai.extract.call_count, 40)
        ai.reset_mock()
        collector.collect(self.state, args, ai)
        ai.extract.assert_not_called()
        ai.discover.assert_not_called()

    def test_stalled_discovery_reports_shortfall(self):
        ai = Mock()
        ai.discover.return_value = []
        with contextlib.redirect_stdout(io.StringIO()):
            reason = collector.collect(self.state, collector.parse_args([]), ai)
        report = collector.export(self.state, 2000, reason)
        self.assertEqual(ai.discover.call_count, 3)
        ai.extract.assert_not_called()
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["shortfall"], 2000)

    def test_two_duplicate_batches_stop_thread_and_pass_seen_text(self):
        self.state.add_threads([URL])
        ai = Mock()
        ai.extract.return_value = batch([fixture(1)])
        ai.discover.return_value = []
        with contextlib.redirect_stdout(io.StringIO()):
            collector.collect(self.state, collector.parse_args([]), ai)
        self.assertEqual(ai.extract.call_count, 3)
        self.assertEqual(ai.extract.call_args.args[4][0]["text_start"], fixture(1)["comment_text"])
        row = self.state.db.execute("SELECT * FROM threads").fetchone()
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["stalled_batches"], 2)

    def test_increasing_per_thread_limit_continues_limited_threads(self):
        self.state.add_threads([URL])
        ai = Mock()
        ai.extract.side_effect = [batch([fixture(1)]), batch([fixture(2)])]
        ai.discover.return_value = []
        with contextlib.redirect_stdout(io.StringIO()):
            collector.collect(self.state, collector.parse_args(["--count", "2", "--max-batches-per-thread", "1"]), ai)
        self.assertEqual(self.state.db.execute("SELECT status FROM threads").fetchone()[0], "limited")
        with contextlib.redirect_stdout(io.StringIO()):
            collector.collect(self.state, collector.parse_args(["--count", "2", "--max-batches-per-thread", "2"]), ai)
        self.assertEqual(self.state.accepted_count(), 2)

    def test_request_budget_stop_keeps_thread_pending(self):
        self.state.add_threads([URL])
        ai = Mock()
        ai.extract.side_effect = collector.StopCollection("request limit reached")
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(collector.StopCollection):
            collector.collect(self.state, collector.parse_args([]), ai)
        row = self.state.db.execute("SELECT * FROM threads").fetchone()
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["batches"], 0)

    def test_five_unavailable_threads_stop_and_record_failures(self):
        self.state.add_threads([URL.replace("abc123", f"abc{i}") for i in range(6)])
        ai = Mock()
        ai.extract.side_effect = collector.ThreadUnavailable("Unreadable comments")
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(collector.StopCollection, "Five successive"):
            collector.collect(self.state, collector.parse_args([]), ai)
        self.assertEqual(self.state.db.execute("SELECT COUNT(*) FROM threads WHERE status='failed'").fetchone()[0], 5)
        self.assertEqual(self.state.db.execute("SELECT COUNT(*) FROM threads WHERE status='pending'").fetchone()[0], 1)

    def test_empty_old_checkpoint_upgraded_preserving_seed_threads(self):
        self.state.add_threads([URL])
        self.state.set_meta("config", dict(self.config, schema_version=1))
        with self.state.db:
            self.state.db.execute("UPDATE threads SET status='failed',error='old Reddit error'")
        self.state.db.close()
        self.state = collector.State(self.folder, self.config)
        self.assertEqual(self.state.get_meta("config")["schema_version"], 2)
        self.assertEqual(self.state.get_meta("previous_config")["schema_version"], 1)
        self.assertEqual(self.state.db.execute("SELECT status FROM threads").fetchone()[0], "pending")

    def test_nonempty_old_collection_and_config_mismatch_preserved(self):
        self.state.add_comments([fixture(1)], 3)
        self.state.set_meta("config", dict(self.config, schema_version=1))
        with self.assertRaisesRegex(collector.StopCollection, "new --out"):
            collector.State(self.folder, self.config)
        self.assertEqual(self.state.accepted_count(), 1)
        with self.assertRaises(collector.StopCollection):
            collector.State(self.folder, dict(self.config, topic="another topic"))

    def test_actual_sdk_extraction_request_and_saved_audit(self):
        requests = []
        def handle(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=response_data(extraction_text()))
        ai = collector.OpenAIService(self.state, "gpt-5.5", 2, client=self.client(handle))
        result = ai.extract("BMW G60", "sedan", THREAD, 30, [])
        self.assertEqual(result.rows[0]["comment_text"], raw_comment()["comment_text"])
        self.assertFalse(requests[0]["store"])
        self.assertEqual(requests[0]["tool_choice"], "required")
        self.assertEqual(requests[0]["tools"][0]["type"], "web_search")
        self.assertEqual(requests[0]["tools"][0]["filters"]["allowed_domains"], ["reddit.com"])
        self.assertEqual(requests[0]["include"], ["web_search_call.action.sources"])
        self.assertEqual(requests[0]["reasoning"], {"effort": "low"})
        self.assertTrue((self.folder / result.response_file).exists())
        self.assertEqual(self.state.db.execute("SELECT input_tokens FROM api_calls").fetchone()[0], 20)

    def test_actual_sdk_discovery_request(self):
        client = self.client(lambda _: httpx.Response(200, json=response_data()))
        ai = collector.OpenAIService(self.state, "gpt-5.5", 2, client=client)
        self.assertEqual(ai.discover("BMW G60", "sedan", []), [URL])
        self.assertEqual(self.state.get_meta("discovery_round"), 1)

    def test_retry_respects_request_budget(self):
        calls = []
        def handle(request):
            calls.append(request)
            return httpx.Response(429, headers={"retry-after": "0"},
                                  json={"error": {"message": "synthetic rate limit", "type": "rate_limit_error"}})
        ai = collector.OpenAIService(self.state, "gpt-5.5", 1, client=self.client(handle), sleep=lambda _: None)
        with self.assertRaisesRegex(collector.StopCollection, "request limit"):
            ai.request("test", input="test")
        self.assertEqual(len(calls), 1)

    def test_incomplete_response_saved_without_accepting_rows(self):
        client = self.client(lambda _: httpx.Response(200, json=response_data(extraction_text(), status="incomplete")))
        ai = collector.OpenAIService(self.state, "gpt-5.5", 2, client=client)
        with self.assertRaisesRegex(collector.StopCollection, "incomplete"):
            ai.extract("BMW G60", "sedan", THREAD, 30, [])
        self.assertEqual(self.state.accepted_count(), 0)
        self.assertEqual(len(list((self.folder / "api_responses").glob("*.json"))), 1)

    def test_cli_requires_only_openai_key_and_retry_failed_resets_progress(self):
        self.state.add_threads([URL])
        with self.state.db:
            self.state.db.execute("UPDATE threads SET status='failed',batches=2,stalled_batches=1")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-key"}, clear=True), \
             patch.object(collector, "OpenAIService") as service, \
             patch.object(collector, "collect", return_value="synthetic stop") as collect, \
             contextlib.redirect_stdout(io.StringIO()):
            code = collector.main(["--out", str(self.folder), "--retry-failed"])
        self.assertEqual(code, 2)
        service.assert_called_once()
        collect.assert_called_once()
        row = self.state.db.execute("SELECT * FROM threads WHERE id='abc123'").fetchone()
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["batches"], 0)

    def test_missing_key_cli_has_no_reddit_credential_requirement(self):
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            code = collector.main(["--out", str(self.folder / "cli"), "--topic", "Synthetic topic"])
        self.assertEqual(code, 1)
        report = json.loads((self.folder / "cli" / "run_report.json").read_text())
        self.assertEqual(report["status"], "partial")
        self.assertIn("OPENAI_API_KEY", report["reason"])
        self.assertNotIn("REDDIT_CLIENT", report["reason"])
        self.assertEqual(report["openai_usage_all_runs"]["requests"], 0)


if __name__ == "__main__":
    unittest.main()
