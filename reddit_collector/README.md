# Reddit comment collector without the Reddit API

Collect Reddit comment quotations about BMW G60 or another topic using **OpenAI web search**. Only `OPENAI_API_KEY` is required. The script no longer uses PRAW, Reddit app credentials, or Reddit API endpoints.

It asks OpenAI to read public Reddit pages, quote complete relevant comments, and return source links. **These are model-extracted quotations, not independently verified original comment bodies.** The script checks that the thread appears in web-search source metadata; this does not prove the quoted text, author or date is correct. Every row is marked `unverified_model_extraction` and linked to the saved OpenAI response for review.

The script targets 2,000 unique quotation texts and preserves partial results. It cannot guarantee 2,000 accessible or accurate comments on every run. It reports the exact shortfall instead of padding the output.

## Setup in PowerShell

Requires Python 3.10+ and an OpenAI API project with web-search access and available billing/credits. Create a key in the [OpenAI API dashboard](https://platform.openai.com/api-keys). ChatGPT/Codex sign-in does not supply this script's API key.

From `C:\Users\toham\Code\EHL`:

```powershell
python -m pip install -r reddit_collector/requirements.txt
$env:OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
python reddit_collector/collect_reddit.py --topic "BMW G60" --count 2000
```

Replace the placeholder with your key. This sets it for the current PowerShell window; keep it out of source files and shared logs. You can leave any previously configured Reddit variables alone: the script ignores them.

The default model is `gpt-5.5`. Use `--model` or `OPENAI_MODEL` to select another model available to your API project that supports Responses web search **and opening pages**. A model limited to search snippets cannot reliably read comment threads. See the [OpenAI web-search guide](https://developers.openai.com/api/docs/guides/tools-web-search).

OpenAI requests and web searches incur charges. Request limits are not dollar limits, and a single request can perform several web searches. Repeated runs can incur additional charges.

## Output and resume

The default folder is `reddit_collector/output/bmw_g60/`:

| File | Contents |
|---|---|
| `comments.csv` | Spreadsheet export with quotations, source links and provenance |
| `comments.jsonl` | Model-extracted text preserved unchanged, one JSON object per line |
| `comments.md` | Numbered quotations with clickable source-thread links |
| `run_report.json` | Count, shortfall, thread progress, limits, token usage and limitations |
| `checkpoint.sqlite3` | Saved rows, queued threads and extraction progress |
| `api_responses/` | OpenAI responses used for discovery/extraction, including source metadata |

Rows include the text, displayed username/date when available, thread details, retrieval time, local text hash, extraction model, and response-file reference. The local `web_...` row ID is **not** a Reddit comment ID. Posting timestamps, scores, parent IDs and individual comment permalinks are not inferred. Source links identify the thread; they are not proof of an individual comment's existence. Unknown displayed metadata is stored as null.

The JSONL retains model-returned text; it does not certify that text matches Reddit. The CSV prefixes formula-like fields with an apostrophe for spreadsheet use. The Markdown escapes comment formatting and links to the source thread.

Run the same command to resume. Saved rows are reused, and pending threads continue. If the target is already saved, exporting it requires no API calls or key. Surplus rows remain in the checkpoint even when the requested export count is smaller.

Your previous **empty** checkpoint is upgraded automatically. An older checkpoint containing Reddit API comments requires a new `--out` folder so differently sourced datasets are not silently combined. Changing the topic, scope, minimum word count or subreddit restrictions also requires a different folder:

```powershell
python reddit_collector/collect_reddit.py --topic "BMW i4" --count 2000 --out reddit_collector/output/bmw_i4
```

Run one process per output folder. Close the CSV in Excel before rerunning to avoid export locks. Saved quotations are snapshots; resuming does not refresh existing rows for later edits or deletions.

## How collection works

1. For BMW G60, load the 66 thread URLs in `seeds_bmw_g60.txt`. These supply starting points, not saved comment text. Other topics start with discovery unless you provide seeds.
2. Ask OpenAI web search to read a thread and extract up to 30 complete, relevant comments. Prior text prefixes are supplied to help avoid repeats. The prompt excludes original posts, bots, unrelated discussion, incomplete snippets and invented text.
3. Require a completed web-search call and matching thread source metadata. Validate each returned row, then deduplicate by case/whitespace-normalized text. Reject short, deleted, removed and AutoModerator bodies.
4. Save each successful batch and rotate through queued threads. Further passes suggest different public sort views; these are repeated extraction attempts, not guaranteed pagination or access to every reply.
5. Find additional source threads through web search when the queue is exhausted. Stop at the target or configured limits, saving the partial count either way.

A thread is marked `done` after two passes without new rows, or `limited` when its pass limit is reached. Neither means every Reddit comment was read. Five successive unavailable/invalid extractions stop the invocation to avoid spending through a large inaccessible queue. Failed responses remain available for inspection.

Text-only deduplication can merge identical comments from different users. Model transcription differences can also cause one real comment to appear more than once. Relevance classification can be wrong. Search ranking and public page visibility produce a convenience sample, not a representative survey. Review the sources before treating the output as research evidence.

## Controls

| Option | Default | Meaning |
|---|---:|---|
| `--count` | 2000 | Target number of unique quotation texts in the export |
| `--max-api-calls` | 150 | OpenAI HTTP attempts per invocation, including retries |
| `--max-thread-batches` | 200 | Thread extraction attempts per invocation |
| `--max-batches-per-thread` | 4 | Passes per thread across resumes; raising it continues `limited` threads |
| `--max-search-rounds` | 25 | Discovery rounds per invocation; three empty rounds stop early |
| `--batch-size` | 30 | Maximum comments per extraction request; maximum 50 |
| `--min-words` | 3 | Minimum whitespace-separated word count |

`--max-threads` remains an alias for `--max-thread-batches`. The former Reddit `--more-limit` option is removed.

```powershell
# Allow more requests/passes if the saved collection is short.
python reddit_collector/collect_reddit.py --topic "BMW G60" --count 2000 --max-api-calls 250 --max-batches-per-thread 6

# Add source threads and retry threads that previously failed.
python reddit_collector/collect_reddit.py --topic "BMW G60" --count 2000 --seed-file extra_threads.txt --retry-failed
```

Seed files contain one full public Reddit thread URL per line. `--seed-file` can be repeated. `--subreddits BMW BMWi5` restricts communities. `--scope` sets inclusion/exclusion instructions; the default BMW G60 scope includes the i5 sedan and comparisons, while excluding G61 touring, G68 and M5-only discussions.

Transient API failures retry within the request budget. Interrupted or incomplete API batches remain pending. If extraction is repeatedly unreadable, inspect `api_responses/` and `run_report.json` before raising limits. Repeating a failed request is not a guarantee that the source will become available. Usage totals are not a billing ledger; timeouts can consume usage without returning token totals.

Exit codes: `0` = quotation-count target reached; `2` = partial due to discovery/batch limits; `1` = configuration/API/storage error or request limit; `130` = interrupted. `target_reached` describes the row count, not independent verification of quotations.

## Verification

```powershell
python -m unittest discover -s reddit_collector/tests -v
```

The 22 offline tests cover source checks, malformed extraction, deduplication, a synthetic 2,000-row export, resume, old empty checkpoint migration, one-key setup, actual SDK serialization with mocked HTTP, rate limits and incomplete responses. A live collection has not been tested in this workspace because `OPENAI_API_KEY` is unavailable.
