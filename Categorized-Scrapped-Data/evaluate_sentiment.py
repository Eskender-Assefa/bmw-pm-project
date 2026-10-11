#!/usr/bin/env python3
"""Measure live sentiment scores and optional category/discard expectations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI, OpenAIError

from categorize_comments import CATEGORIES, DEFAULT_MODEL, classify_comment, read_jsonl, valid_sentiment_score


DEFAULT_CASES = Path(__file__).resolve().parent / "evals" / "sentiment_cases.jsonl"


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = []
    identifiers = set()
    for line_number, case in read_jsonl(path):
        if (
            not isinstance(case.get("case_id"), str)
            or not case["case_id"].strip()
            or case["case_id"] in identifiers
            or not isinstance(case.get("comment_text"), str)
            or not valid_sentiment_score(case.get("min_score"))
            or not valid_sentiment_score(case.get("max_score"))
            or case["min_score"] > case["max_score"]
            or (
                "expected_category" in case
                and case["expected_category"] is not None
                and case["expected_category"] not in CATEGORIES
            )
        ):
            raise ValueError(
                f"{path}:{line_number}: expected a unique case_id, comment_text, "
                "and -100 <= min_score <= max_score <= 100; optional "
                "expected_category must be a category name or null (discard)"
            )
        identifiers.add(case["case_id"])
        cases.append(case)
    if not cases:
        raise ValueError(f"{path}: no evaluation cases found")
    return cases


def evaluate_cases(client: OpenAI, cases: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    results = []
    for case in cases:
        category, score = classify_comment(client, case["comment_text"], model)
        minimum, maximum = case["min_score"], case["max_score"]
        category_matches = "expected_category" not in case or category == case["expected_category"]
        passed = minimum <= score <= maximum and category_matches
        results.append({
            **case,
            "model": model,
            "categorie": category,
            "sentiment_score": score,
            "passed": passed,
            "category_matches": category_matches,
            "distance_outside_range": max(minimum - score, 0, score - maximum),
        })
        category_detail = (
            f", category={category!r}, expected_category={case['expected_category']!r}"
            if "expected_category" in case else ""
        )
        print(
            f"{'PASS' if passed else 'FAIL'} {case['case_id']}: "
            f"score={score:g}, expected=[{minimum:g}, {maximum:g}]{category_detail}",
            file=sys.stderr,
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="JSONL with expected score ranges")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--report", type=Path, help="Write a new JSONL report; existing files are protected")
    args = parser.parse_args(argv)
    try:
        cases = load_cases(args.cases)
        if args.report and args.report.exists():
            raise FileExistsError(f"{args.report} already exists; choose a new report path")
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            raise ValueError("Set OPENAI_API_KEY to run the live evaluation (API usage is billed)")
        with OpenAI(timeout=60.0, max_retries=3) as client:
            results = evaluate_cases(client, cases, args.model)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            with args.report.open("x", encoding="utf-8", newline="\n") as destination:
                for result in results:
                    destination.write(json.dumps(result, ensure_ascii=False) + "\n")
    except OpenAIError as exc:
        print(f"Error: {type(exc).__name__} (HTTP {getattr(exc, 'status_code', 'n/a')})", file=sys.stderr)
        return 2
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nEvaluation interrupted.", file=sys.stderr)
        return 130

    passed = sum(result["passed"] for result in results)
    mean_distance = sum(result["distance_outside_range"] for result in results) / len(results)
    print(f"{passed}/{len(results)} cases passed ({passed / len(results):.1%}).")
    print(f"Mean distance outside expected range: {mean_distance:.2f} points.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
