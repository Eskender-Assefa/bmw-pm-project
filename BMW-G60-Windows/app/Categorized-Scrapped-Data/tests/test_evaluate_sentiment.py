import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import evaluate_sentiment as evaluation


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cases_path = Path(self.temp.name) / "cases.jsonl"
        self.report_path = Path(self.temp.name) / "report.jsonl"

    def write_cases(self, cases):
        self.cases_path.write_text(
            "".join(json.dumps(case) + "\n" for case in cases), encoding="utf-8"
        )

    def test_grading_uses_inclusive_ranges_without_sending_answers_to_model(self):
        cases = [
            {"case_id": "lower_edge", "comment_text": "First", "min_score": -100, "max_score": -90},
            {"case_id": "upper_edge", "comment_text": "Second", "min_score": 90, "max_score": 100},
            {"case_id": "neutral", "comment_text": "Third", "min_score": 0, "max_score": 0},
            {"case_id": "too_high", "comment_text": "Fourth", "min_score": -70, "max_score": -30},
            {"case_id": "too_low", "comment_text": "Fifth", "min_score": 30, "max_score": 70},
        ]
        client = object()
        scores = [-100, 100, 0, -12.5, 10]
        with (
            patch.object(evaluation, "classify_comment", side_effect=[("Comfort", x) for x in scores]) as classifier,
            redirect_stderr(io.StringIO()),
        ):
            results = evaluation.evaluate_cases(client, cases, "test-model")
        self.assertEqual([result["passed"] for result in results], [True, True, True, False, False])
        self.assertEqual([result["distance_outside_range"] for result in results], [0, 0, 0, 17.5, 20])
        self.assertEqual(classifier.call_args_list, [
            call(client, case["comment_text"], "test-model") for case in cases
        ])

    def test_case_validation_rejects_invalid_ranges_and_duplicate_ids(self):
        valid = {"case_id": "one", "comment_text": "Comment", "min_score": -20, "max_score": 20}
        for cases in [
            [], [valid, valid], [{**valid, "min_score": 50}], [{**valid, "max_score": 101}],
            [{**valid, "min_score": True}], [{**valid, "max_score": float("nan")}],
            [{**valid, "comment_text": None}], [{**valid, "case_id": ""}],
            [{**valid, "expected_category": "Discard"}], [{**valid, "expected_category": []}],
        ]:
            with self.subTest(cases=cases):
                self.write_cases(cases)
                with self.assertRaises(ValueError):
                    evaluation.load_cases(self.cases_path)

    def test_starter_cases_have_valid_ranges(self):
        cases = evaluation.load_cases(evaluation.DEFAULT_CASES)
        self.assertEqual(len(cases), 22)

    def test_relevance_cases_have_valid_category_expectations(self):
        cases = evaluation.load_cases(evaluation.DEFAULT_CASES.with_name("relevance_cases.jsonl"))
        self.assertTrue(all("expected_category" in case for case in cases))
        self.assertTrue(any(case["expected_category"] is None for case in cases))
        self.assertTrue(any(case["expected_category"] == "Miscellaneous" for case in cases))

    def test_category_expectations_grade_discard_and_keep_without_sending_answers(self):
        cases = [
            {"case_id": "discard", "comment_text": "Yay", "min_score": -100, "max_score": 100, "expected_category": None},
            {"case_id": "keep", "comment_text": "Add a fridge", "min_score": -100, "max_score": 100, "expected_category": "Miscellaneous"},
            {"case_id": "wrongly_kept", "comment_text": "First!", "min_score": -100, "max_score": 100, "expected_category": None},
            {"case_id": "wrongly_discarded", "comment_text": "Add a fridge", "min_score": -100, "max_score": 100, "expected_category": "Miscellaneous"},
        ]
        self.write_cases(cases)
        client = object()
        with (
            patch.object(evaluation, "classify_comment", side_effect=[
                (None, 25), ("Miscellaneous", 0), ("Miscellaneous", 0), (None, 0),
            ]) as classifier,
            redirect_stderr(io.StringIO()),
        ):
            results = evaluation.evaluate_cases(client, evaluation.load_cases(self.cases_path), "test-model")
        self.assertEqual([result["passed"] for result in results], [True, True, False, False])
        self.assertEqual(classifier.call_args_list, [
            call(client, case["comment_text"], "test-model") for case in cases
        ])

    def test_cli_reports_failures_and_saves_scores(self):
        self.write_cases([
            {"case_id": "neutral", "comment_text": "Question", "min_score": 0, "max_score": 0},
            {"case_id": "negative", "comment_text": "Complaint", "min_score": -80, "max_score": -40},
        ])
        stdout = io.StringIO()
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-not-real"}),
            patch.object(evaluation, "OpenAI", return_value=MagicMock()),
            patch.object(evaluation, "classify_comment", side_effect=[("Interior Design", 0), ("Software", 20)]),
            redirect_stdout(stdout), redirect_stderr(io.StringIO()),
        ):
            code = evaluation.main(["--cases", str(self.cases_path), "--report", str(self.report_path)])
        self.assertEqual(code, 1)
        self.assertIn("1/2 cases", stdout.getvalue())
        self.assertIn("30.00 points", stdout.getvalue())
        rows = [json.loads(line) for line in self.report_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["passed"] for row in rows], [True, False])
        self.assertEqual(rows[1]["sentiment_score"], 20)

    def test_cli_without_key_does_not_call_api_or_create_report(self):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": ""}),
            patch.object(evaluation, "OpenAI") as client,
            redirect_stderr(io.StringIO()),
        ):
            code = evaluation.main(["--report", str(self.report_path)])
        self.assertEqual(code, 2)
        client.assert_not_called()
        self.assertFalse(self.report_path.exists())

    def test_cli_preserves_existing_report_before_any_api_calls(self):
        self.report_path.write_text("Keep this report", encoding="utf-8")
        with patch.object(evaluation, "OpenAI") as client, redirect_stderr(io.StringIO()):
            code = evaluation.main(["--report", str(self.report_path)])
        self.assertEqual(code, 2)
        client.assert_not_called()
        self.assertEqual(self.report_path.read_text(encoding="utf-8"), "Keep this report")


if __name__ == "__main__":
    unittest.main()
