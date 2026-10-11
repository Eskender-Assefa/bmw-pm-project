# Categorize automotive comments

`categorize_comments.py` reads a JSONL file, discards irrelevant comments, and
classifies and scores retained comments using the OpenAI API. It writes one JSON object per line with
exactly these fields:

```text
row_id | categorie | comment | date_displayed | sentiment_score
```

The pipes above separate field names; the files themselves are **JSONL**, with no
header row. The spelling `categorie` is intentional. `comment` is copied from
`comment_text`; the original text, `row_id`, and `date_displayed` are preserved.
Retained rows stay in their original order.

Comments must discuss a specific category or a concrete vehicle feature or idea
to be kept. For example, **"Omg it’s another accord. Yay" is discarded**, while
**"They should put a fridge in the car" is kept as Miscellaneous**. Generic
reactions, off-topic chatter, and brand/model mentions without a substantive
topic are omitted. Facts, questions, short feature opinions, and ideas for
features the car does not yet have are still relevant. A reaction followed by
a real feature comment is retained and classified by that topic.

## Run (PowerShell, Python 3.10+)

```powershell
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "your-openai-api-key"
python categorize_comments.py input.jsonl categorized.jsonl
```

Replace `input.jsonl` with your input file's path. Quote paths containing spaces.
The key is read from the environment; `.env` files are not loaded automatically.

The default model is `gpt-4.1-mini`. To choose another model that supports
Structured Outputs through the Responses API:

```powershell
python categorize_comments.py input.jsonl categorized.jsonl --model gpt-4.1-mini
```

Only `comment_text` is sent to OpenAI. The script gets both category and sentiment
in one request per nonblank comment and saves each completed row immediately.
The SDK retries transient request failures up to three times. If a run fails or
is interrupted, continue it:

```powershell
python categorize_comments.py input.jsonl categorized.jsonl --resume
```

Resuming verifies saved IDs, comments, dates, categories, sentiment scores, and
discard decisions against a prefix of the input, then skips all processed rows.
Keep the companion `categorized.jsonl.discarded.jsonl` file alongside the output.
It stores positions and source hashes for discarded rows, without their comment
text, so discarded rows (including a discarded tail or an entirely discarded
input) are not sent to the API again on resume. The name follows your output
filename. Older output without this companion file can still resume if its rows
match an unfiltered prefix of the input.
Use the same model when resuming; output
does not contain model metadata. To reclassify everything, choose a new output
filename. Existing files are never overwritten.

After changing the filtering/scoring prompt or model, use a new output filename
to reprocess all comments. `--resume` retains existing categories, scores, and
discard decisions. To remove irrelevant Miscellaneous rows from an older output,
rerun the original input into a new output filename.

Older output files without `sentiment_score` cannot be resumed. Run the original
input again with a new output filename to include sentiment on every row.

## Input and output

Each input object must have `row_id`, a string `comment_text`, and
`date_displayed`. Your other fields (`author`, `thread_id`, `thread_title`,
`thread_url`, `source_url`, `subreddit`, `retrieved_at_utc`, `text_sha256`,
`extraction_method`, `text_verification`, `extraction_model`, `source_response_id`,
`source_response_file`) are accepted and omitted from the output.

Example input line (shortened to show the required fields):

```json
{"row_id":"r1","comment_text":"The seats are comfortable on long trips.","date_displayed":"2026-10-11"}
```

Illustrative output:

```json
{"row_id":"r1","categorie":"Comfort","comment":"The seats are comfortable on long trips.","date_displayed":"2026-10-11","sentiment_score":50}
```

Blank input lines are ignored. Unicode, quotes, pipes, and escaped newlines within
retained comments are preserved. Empty or whitespace-only comments are discarded
without an API call. Malformed JSON,
missing required fields, and non-string comments are reported with line numbers
before API requests begin.
API failures, refusals, and invalid model output stop the run with an error;
they are not assigned a fallback category. Completed rows remain available for
`--resume`.

## Sentiment

`sentiment_score` is a number from **-100 to 100**, inclusive:

- **-100:** very negative.
- **0:** neutral specifications, genuine information questions, or an explicitly
  balanced appraisal. A calmly described malfunction can still be negative.
- **100:** very positive.
- Any value in between, including decimals (for example, `-42.5` or `68`), reflects
  the strength of the sentiment.

The prompt includes anchors at 25-point intervals and scored examples for mild
and strong opinions, negation, sarcasm, implied complaints, quoted opinions, and
mixed verdicts. These anchors guide intensity; intermediate scores remain valid.
The score reflects the author's overall appraisal of the vehicle, feature, or
ownership experience across the comment, not just the selected category.

The score measures sentiment, not confidence in the chosen category. The model
does not infer that a raw price or specification is good or bad without evidence
in the comment. The default GPT-4.1 model family uses `temperature=0` to reduce
sampling variability; results are not guaranteed to be identical across runs.
Both the response schema and local validation enforce the numeric range, but
accuracy must be checked against examples labeled to match your expectations.

The use of diverse scored examples follows OpenAI's
[few-shot prompting guidance](https://developers.openai.com/api/docs/guides/prompt-engineering#few-shot-learning).

## Evaluate sentiment accuracy

The normal unit tests use mocked responses, so they do **not** measure how well
the model understands sentiment. To test real scores using your configured API
key, run:

```powershell
python evaluate_sentiment.py --report sentiment-evaluation.jsonl
```

This makes real, billed API calls on 22 synthetic cases in
`evals/sentiment_cases.jsonl`, distinct from the examples in the prompt. It prints
each score and expected range, plus the fraction of cases within range and mean
distance outside the expected ranges. Exit code is 0 when all cases pass, 1 for
score mismatches, and 2 for configuration or API errors. Existing reports are
protected; choose a new report filename for another run.

These starter cases and ranges are proposed calibration targets, not a validated
benchmark for your dataset. Add or supply real comments and ranges you have
reviewed yourself, as recommended in OpenAI's
[evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices):

```json
{"case_id":"my_example","comment_text":"The seats are a bit too firm for me.","min_score":-35,"max_score":-15}
```

```powershell
python evaluate_sentiment.py --cases my_sentiment_cases.jsonl --report my-evaluation.jsonl
```

Use `--model` with the evaluator to compare models on the same reviewed cases.
Expected ranges are used only for grading and are not sent in the model request.

## Evaluate relevance filtering

The same evaluator supports `expected_category`, using JSON `null` to mean
discard. Check the Accord/fridge distinction, generic reactions, neutral feature
facts, mixed comments, and German examples with:

```powershell
python evaluate_sentiment.py --cases evals/relevance_cases.jsonl --report relevance-evaluation.jsonl
```

These 19 cases make 18 real, billed API calls; the blank comment is handled
locally. A case passes only when its category/discard decision and sentiment
range both match. Most relevance cases allow the full sentiment range to focus
on filtering. Expected categories are used only for grading, never sent to the
model. These are starter acceptance cases, not a validated dataset benchmark.

## Categories

Each retained comment receives exactly one category. For multiple topics, the prompt
asks for the dominant concern; equally prominent topics use the first
substantive topic discussed.

| Category | Topics |
| --- | --- |
| Power & Performance | Power, torque, acceleration, handling, drivetrain, towing |
| Energy & Emissions | Efficiency, battery, range, charging, emissions |
| Price | Price, affordability, value, financing, ownership costs |
| Safety | Crash protection, hazards, visibility, collision avoidance |
| Comfort | Seat comfort, ride, noise, climate, legroom |
| Exterior | Exterior styling, paint, body shape, lights, wheels |
| Software | Infotainment, navigation, apps, connectivity, updates, bugs |
| Interior Design | Cabin aesthetics, materials, trim, physical layout, storage |
| Automation | Cruise control, lane keeping, automated parking, self-driving |
| Miscellaneous | Concrete vehicle features or new feature ideas outside the other categories, such as an onboard fridge |

The request uses [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
with a strict enum of these ten labels plus `null` for the internal discard
decision. Discarded comments are omitted from the output; no extra output field
or discard category is added. [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
supports Structured Outputs. The schema restricts label formatting; semantic
classification still depends on the model and comment context.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests use the installed OpenAI SDK with a mock HTTP transport. They require no
API key and make no network requests.
