import io
import json
import os
import tempfile
import unittest
from collections import deque
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import httpx
from openai import OpenAI

import categorize_comments as app


def response_body(category="Comfort", *, sentiment_score=70, status="completed", refusal=False, text=None):
    content = (
        {"type": "refusal", "refusal": "Cannot classify this comment."}
        if refusal
        else {
            "type": "output_text",
            "text": text if text is not None else json.dumps({
                "categorie": category, "sentiment_score": sentiment_score,
            }),
            "annotations": [],
        }
    )
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 1,
        "model": app.DEFAULT_MODEL,
        "status": status,
        "output": [{
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [content],
        }],
    }


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.input = self.folder / "input.jsonl"
        self.output = self.folder / "output.jsonl"
        self.replies = deque()
        self.requests = []
        self.client = OpenAI(
            api_key="test-key-not-real",
            max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(self.handle_request)),
        )
        self.addCleanup(self.client.close)

    def handle_request(self, request):
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url.path, "/v1/responses")
        self.requests.append(json.loads(request.content))
        self.assertTrue(self.replies, "Unexpected API request")
        return self.replies.popleft()

    def reply(self, category="Comfort", **kwargs):
        self.replies.append(httpx.Response(200, json=response_body(category, **kwargs)))

    def write_input(self, rows):
        self.input.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )

    def read_output(self):
        return [json.loads(line) for line in self.output.read_text(encoding="utf-8").splitlines()]

    def convert(self, **kwargs):
        with redirect_stderr(io.StringIO()):
            return app.convert_jsonl(self.input, self.output, self.client, **kwargs)

    def test_preserves_values_order_and_exact_field_names_through_sdk(self):
        rows = [
            {
                "row_id": "0001",
                "comment_text": 'Great acceleration | "sehr schön" 🚗\nStill smooth.',
                "date_displayed": "2 days ago",
                "author": "private-author",
                "thread_title": "Other metadata should not be sent",
                "source_url": "https://example.invalid/private",
            },
            {"row_id": 2, "comment_text": "Too expensive.", "date_displayed": None},
        ]
        # A UTF-8 BOM and blank lines are common in exported files.
        self.input.write_text(
            "\n" + "\n\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8-sig",
        )
        self.reply("Power & Performance", sentiment_score=85.5)
        self.reply("Price", sentiment_score=-60)
        self.assertEqual(self.convert(model="custom-compatible-model"), 2)
        actual = self.read_output()
        for original, converted, category, score in zip(
            rows, actual, ("Power & Performance", "Price"), (85.5, -60)
        ):
            self.assertEqual(list(converted), [
                "row_id", "categorie", "comment", "date_displayed", "sentiment_score",
            ])
            self.assertEqual(converted, {
                "row_id": original["row_id"],
                "categorie": category,
                "comment": original["comment_text"],
                "date_displayed": original["date_displayed"],
                "sentiment_score": score,
            })
        request = self.requests[0]
        self.assertEqual(request["model"], "custom-compatible-model")
        self.assertNotIn("temperature", request)
        self.assertFalse(request["store"])
        self.assertEqual(request["input"][0]["role"], "user")
        self.assertEqual(json.loads(request["input"][0]["content"]), {"comment_text": rows[0]["comment_text"]})
        schema = request["text"]["format"]
        self.assertTrue(schema["strict"])
        self.assertFalse(schema["schema"]["additionalProperties"])
        self.assertEqual(schema["schema"]["properties"]["categorie"]["enum"], [
            "Power & Performance", "Energy & Emissions", "Price", "Safety", "Comfort",
            "Exterior", "Software", "Interior Design", "Automation", "Miscellaneous", None,
        ])
        self.assertEqual(schema["schema"]["properties"]["categorie"]["type"], ["string", "null"])
        self.assertEqual(schema["schema"]["properties"]["sentiment_score"], {
            "type": "number", "minimum": -100, "maximum": 100,
        })
        self.assertEqual(schema["schema"]["required"], ["categorie", "sentiment_score"])
        self.assertEqual(len(self.requests), 2)

    def test_whitespace_comments_are_discarded_without_api_calls_and_stay_processed(self):
        self.write_input([
            {"row_id": 1, "comment_text": "", "date_displayed": ""},
            {"row_id": 2, "comment_text": " \n\t", "date_displayed": None},
        ])
        self.assertEqual(self.convert(), 0)
        self.assertEqual(self.read_output(), [])
        self.assertEqual(self.convert(resume=True), 0)
        self.assertEqual(self.requests, [])

    def test_discarded_reactions_are_omitted_and_feature_ideas_are_kept(self):
        rows = [
            {"row_id": 1, "comment_text": "Omg it’s another accord. Yay", "date_displayed": "today"},
            {"row_id": 1, "comment_text": "They should put a fridge in the car.", "date_displayed": "today"},
            {"row_id": 2, "comment_text": " \n\t", "date_displayed": None},
            {"row_id": 3, "comment_text": "Another Accord, but the seats are comfortable.", "date_displayed": "today"},
            {"row_id": 4, "comment_text": "First!", "date_displayed": "today"},
        ]
        self.write_input(rows)
        self.reply(None, sentiment_score=10)
        self.reply("Miscellaneous", sentiment_score=0)
        self.reply("Comfort", sentiment_score=50)
        self.reply(None, sentiment_score=0)
        self.assertEqual(self.convert(), 2)
        self.assertEqual(self.read_output(), [
            app.output_row(rows[1], "Miscellaneous", 0),
            app.output_row(rows[3], "Comfort", 50),
        ])
        progress_path = app.discard_log_path(self.output)
        progress_text = progress_path.read_text(encoding="utf-8")
        records = [json.loads(line) for line in progress_text.splitlines()]
        self.assertEqual([record["position"] for record in records], [1, 3, 5])
        self.assertNotIn(rows[0]["comment_text"], progress_text)
        self.assertNotIn("First!", progress_text)
        before = self.output.read_bytes(), progress_path.read_bytes()
        self.assertEqual(self.convert(resume=True), 0)
        self.assertEqual((self.output.read_bytes(), progress_path.read_bytes()), before)
        self.assertEqual(len(self.requests), 4)

        # New input after a discarded tail must still be classified.
        rows.append({"row_id": 5, "comment_text": "Too expensive.", "date_displayed": "today"})
        self.write_input(rows)
        self.reply("Price", sentiment_score=-50)
        self.assertEqual(self.convert(resume=True), 1)
        self.assertEqual([row["row_id"] for row in self.read_output()], [1, 3, 5])
        self.assertEqual(len(self.requests), 5)

    def test_all_discarded_comments_resume_without_new_requests(self):
        self.write_input([
            {"row_id": 1, "comment_text": "First!", "date_displayed": "today"},
            {"row_id": 2, "comment_text": "Yay", "date_displayed": "today"},
        ])
        self.reply(None, sentiment_score=0)
        self.reply(None, sentiment_score=25)
        self.assertEqual(self.convert(), 0)
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertEqual(self.convert(resume=True), 0)
        self.assertEqual(len(self.requests), 2)

    def test_failure_after_a_discard_preserves_progress(self):
        self.write_input([
            {"row_id": 1, "comment_text": "Yay", "date_displayed": "today"},
            {"row_id": 1, "comment_text": "A built-in fridge would help.", "date_displayed": "today"},
        ])
        self.reply(None, sentiment_score=25)
        self.reply(status="incomplete")
        with self.assertRaisesRegex(RuntimeError, r"input\.jsonl:2:.*--resume"):
            self.convert()
        self.assertEqual(self.read_output(), [])
        self.reply("Miscellaneous", sentiment_score=0)
        self.assertEqual(self.convert(resume=True), 1)
        self.assertEqual(len(self.requests), 3)
        self.assertEqual(self.read_output()[0]["categorie"], "Miscellaneous")

    def test_changed_discarded_input_is_rejected_before_api_calls(self):
        row = {"row_id": 1, "comment_text": "Yay", "date_displayed": "today"}
        self.write_input([row])
        self.reply(None, sentiment_score=25)
        self.convert()
        for changes in ({"comment_text": "Comfortable seats"}, {"row_id": 2}, {"date_displayed": "yesterday"}):
            with self.subTest(changes=changes):
                self.write_input([{**row, **changes}])
                with self.assertRaisesRegex(ValueError, "discard progress does not match"):
                    self.convert(resume=True)
                self.assertEqual(len(self.requests), 1)

    def test_invalid_discard_progress_is_rejected_before_api_calls(self):
        row = {"row_id": 1, "comment_text": "Yay", "date_displayed": "today"}
        self.write_input([row])
        self.output.write_text("", encoding="utf-8")
        valid = app.discard_record(1, row)
        for content in [
            '{"partial":',
            json.dumps({**valid, "position": True}),
            json.dumps({**valid, "position": 0}),
            json.dumps({**valid, "position": 2}),
            json.dumps({**valid, "source_sha256": "wrong"}),
            json.dumps(valid) + "\n" + json.dumps(valid),
            json.dumps(valid) + "\n" + json.dumps({**valid, "position": 2}),
        ]:
            with self.subTest(content=content):
                app.discard_log_path(self.output).write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.convert(resume=True)
                self.assertEqual(self.requests, [])
                self.assertEqual(self.output.read_bytes(), b"")
                self.assertEqual(app.discard_log_path(self.output).read_text(encoding="utf-8"), content)

    def test_resume_handles_discard_log_without_final_newline(self):
        rows = [
            {"row_id": 1, "comment_text": "Yay", "date_displayed": "today"},
            {"row_id": 2, "comment_text": "First!", "date_displayed": "today"},
        ]
        self.write_input(rows)
        self.output.write_text("", encoding="utf-8")
        progress_path = app.discard_log_path(self.output)
        progress_path.write_text(json.dumps(app.discard_record(1, rows[0])), encoding="utf-8")
        self.reply(None, sentiment_score=0)
        self.assertEqual(self.convert(resume=True), 0)
        self.assertEqual(len(list(app.read_discards(progress_path))), 2)
        self.assertEqual(self.convert(resume=True), 0)
        self.assertEqual(len(self.requests), 1)

    def test_discard_log_cannot_overwrite_input_or_orphaned_progress(self):
        self.input = app.discard_log_path(self.output)
        self.write_input([{"row_id": 1, "comment_text": "Yay", "date_displayed": "today"}])
        before = self.input.read_bytes()
        with self.assertRaisesRegex(ValueError, "different files"):
            self.convert()
        self.assertEqual(self.input.read_bytes(), before)
        self.assertFalse(self.output.exists())
        self.input = self.folder / "input.jsonl"
        self.write_input([{"row_id": 2, "comment_text": "Seats", "date_displayed": "today"}])
        with self.assertRaisesRegex(FileExistsError, "without its output"):
            self.convert(resume=True)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.requests, [])

    def test_input_is_fully_validated_before_requests_or_output_creation(self):
        valid = json.dumps({"row_id": 1, "comment_text": "Good seats", "date_displayed": "today"})
        invalid_rows = [
            "{broken json",
            "[]",
            '{"row_id":2,"comment_text":"No date"}',
            '{"row_id":2,"comment_text":null,"date_displayed":"today"}',
        ]
        for invalid in invalid_rows:
            with self.subTest(invalid=invalid):
                self.input.write_text(valid + "\n" + invalid + "\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, r"input\.jsonl:2:"):
                    self.convert()
                self.assertFalse(self.output.exists())
                self.assertEqual(self.requests, [])

    def test_existing_output_and_input_are_protected(self):
        self.write_input([{"row_id": 1, "comment_text": "Good seats", "date_displayed": "today"}])
        original = self.input.read_bytes()
        with self.assertRaisesRegex(ValueError, "different files"):
            app.convert_jsonl(self.input, self.input, self.client, resume=True)
        self.assertEqual(self.input.read_bytes(), original)
        self.output.write_text("keep existing output", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.convert()
        self.assertEqual(self.output.read_text(encoding="utf-8"), "keep existing output")
        self.assertEqual(self.requests, [])

    def test_resume_handles_missing_final_newline_and_repeated_ids(self):
        self.write_input([
            {"row_id": 1, "comment_text": "Good seats", "date_displayed": "today"},
            {"row_id": 1, "comment_text": "High price", "date_displayed": "yesterday"},
        ])
        saved = {
            "row_id": 1, "categorie": "Comfort", "comment": "Good seats",
            "date_displayed": "today", "sentiment_score": 65.5,
        }
        self.output.write_text(json.dumps(saved), encoding="utf-8")
        self.reply("Price", sentiment_score=-45)
        self.assertEqual(self.convert(resume=True), 1)
        self.assertEqual(len(self.requests), 1)
        actual = self.read_output()
        self.assertEqual(actual[0], saved)
        self.assertEqual(actual[1]["categorie"], "Price")
        self.assertEqual(actual[1]["sentiment_score"], -45)
        before = self.output.read_bytes()
        self.assertEqual(self.convert(resume=True), 0)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(len(self.requests), 1)

    def test_resume_rejects_mismatched_or_invalid_saved_rows(self):
        self.write_input([{"row_id": 1, "comment_text": "Good seats", "date_displayed": "today"}])
        saved = {
            "row_id": 1, "categorie": "Comfort", "comment": "Good seats",
            "date_displayed": "today", "sentiment_score": 70,
        }
        invalid_outputs = [
            json.dumps({**saved, "comment": "Changed text"}),
            json.dumps({**saved, "date_displayed": "different date"}),
            json.dumps({**saved, "categorie": "Unknown"}),
            json.dumps(saved) + "\n" + json.dumps(saved),
            json.dumps(saved) + '\n{"partial":',
        ]
        invalid_outputs.extend(
            json.dumps({**saved, "sentiment_score": score})
            for score in (-100.01, 100.01, "70", None, True, [], {}, float("nan"), float("inf"))
        )
        for content in invalid_outputs:
            with self.subTest(content=content):
                self.output.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.convert(resume=True)
                self.assertEqual(self.output.read_text(encoding="utf-8"), content)
                self.assertEqual(self.requests, [])

    def test_resume_rejects_old_output_without_sentiment(self):
        self.write_input([{"row_id": 1, "comment_text": "Good seats", "date_displayed": "today"}])
        saved = {"row_id": 1, "categorie": "Comfort", "comment": "Good seats", "date_displayed": "today"}
        self.output.write_text(json.dumps(saved) + "\n", encoding="utf-8")
        before = self.output.read_bytes()
        with self.assertRaisesRegex(ValueError, "no sentiment_score.*new output path"):
            self.convert(resume=True)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(self.requests, [])

    def test_api_error_preserves_progress_and_allows_resume(self):
        self.write_input([
            {"row_id": 1, "comment_text": "Good seats", "date_displayed": "today"},
            {"row_id": 2, "comment_text": "Slow charging", "date_displayed": "yesterday"},
        ])
        self.reply()
        self.replies.append(httpx.Response(401, json={"error": {
            "message": "Invalid API key: simulated-secret", "type": "invalid_request_error",
        }}))
        with self.assertRaisesRegex(RuntimeError, r"input\.jsonl:2: AuthenticationError.*--resume") as caught:
            self.convert()
        self.assertNotIn("simulated-secret", str(caught.exception))
        self.assertEqual(len(self.read_output()), 1)
        self.reply("Energy & Emissions")
        self.assertEqual(self.convert(resume=True), 1)
        self.assertEqual([row["row_id"] for row in self.read_output()], [1, 2])

    def test_sdk_retries_transient_rate_limit(self):
        self.write_input([{"row_id": 1, "comment_text": "Good seats", "date_displayed": "today"}])
        self.client.max_retries = 1
        self.replies.append(httpx.Response(
            429,
            headers={"retry-after-ms": "1"},
            json={"error": {"message": "Try again", "type": "rate_limit_error"}},
        ))
        self.reply()
        self.assertEqual(self.convert(), 1)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(len(self.read_output()), 1)

    def test_refusal_incomplete_and_invalid_outputs_are_errors(self):
        for kwargs in [
            {"refusal": True},
            {"status": "incomplete"},
            {"text": "not json"},
            {"text": '[]'},
            {"category": "Unknown"},
            {"category": "Discard"},
            {"category": "null"},
            {"text": '{"categorie":["Comfort"],"sentiment_score":70}'},
            {"text": '{"categorie":"Comfort","sentiment_score":70,"extra":"unwanted"}'},
            {"text": '{"categorie":"Comfort"}'},
            {"text": '{"sentiment_score":70}'},
        ]:
            with self.subTest(kwargs=kwargs):
                self.reply(**kwargs)
                with self.assertRaises(RuntimeError):
                    app.classify_comment(self.client, "Comment", app.DEFAULT_MODEL)

    def test_sentiment_endpoints_neutral_and_intermediate_values_are_preserved(self):
        scores = [-100, -99.99, -42.5, -1, 0, 0.5, 68, 99.99, 100]
        self.write_input([
            {"row_id": i, "comment_text": f"Comment {i}", "date_displayed": "today"}
            for i in range(len(scores))
        ])
        for score in scores:
            self.reply(sentiment_score=score)
        self.assertEqual(self.convert(), len(scores))
        self.assertEqual([row["sentiment_score"] for row in self.read_output()], scores)
        self.assertEqual(len(self.requests), len(scores))

    def test_invalid_sentiment_scores_are_rejected(self):
        for score in (-100.01, 100.01, "70", None, True, False, [], {}, float("nan"), float("inf"), -float("inf")):
            with self.subTest(score=score):
                self.reply(sentiment_score=score)
                with self.assertRaisesRegex(RuntimeError, "invalid sentiment_score"):
                    app.classify_comment(self.client, "Comment", app.DEFAULT_MODEL)

    def test_discard_decisions_still_require_valid_sentiment(self):
        self.reply(None, sentiment_score="irrelevant")
        with self.assertRaisesRegex(RuntimeError, "invalid sentiment_score"):
            app.classify_comment(self.client, "First!", app.DEFAULT_MODEL)

    def test_invalid_sentiment_keeps_completed_rows_and_can_be_resumed(self):
        self.write_input([
            {"row_id": 1, "comment_text": "Good seats", "date_displayed": "today"},
            {"row_id": 2, "comment_text": "Bad seats", "date_displayed": "today"},
        ])
        self.reply(sentiment_score=80)
        self.reply(sentiment_score=-150)
        with self.assertRaisesRegex(RuntimeError, "invalid sentiment_score.*--resume"):
            self.convert()
        self.assertEqual([row["sentiment_score"] for row in self.read_output()], [80])
        self.reply(sentiment_score=-80)
        self.assertEqual(self.convert(resume=True), 1)
        self.assertEqual([row["sentiment_score"] for row in self.read_output()], [80, -80])

    def test_empty_input_creates_empty_output_without_api_calls(self):
        self.input.write_text("\n\n", encoding="utf-8")
        self.assertEqual(self.convert(), 0)
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertEqual(self.requests, [])

    def test_cli_reports_missing_key_without_creating_output(self):
        errors = io.StringIO()
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), redirect_stderr(errors):
            self.assertEqual(app.main([str(self.input), str(self.output)]), 1)
        self.assertIn("OPENAI_API_KEY", errors.getvalue())
        self.assertFalse(self.output.exists())

    def test_cli_runs_with_real_sdk_and_mock_transport(self):
        self.write_input([{"row_id": 1, "comment_text": "Good seats", "date_displayed": "today"}])
        self.reply()
        messages = io.StringIO()
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-not-real"}),
            patch.object(app, "OpenAI", return_value=self.client),
            redirect_stdout(messages),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(app.main([str(self.input), str(self.output)]), 0)
        self.assertIn("Wrote 1 new rows", messages.getvalue())
        self.assertEqual(self.read_output()[0]["categorie"], "Comfort")
        self.assertEqual(self.read_output()[0]["sentiment_score"], 70)
        self.assertEqual(self.requests[0]["temperature"], 0)


if __name__ == "__main__":
    unittest.main()
