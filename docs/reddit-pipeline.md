# Reddit collection from Reviews & Comments

The Next.js page calls the Python API, which queues a job and invokes the two existing Python scripts sequentially. The current repository uses SQLAlchemy with SQLite; this feature follows that configuration and adds no database migration.

## Using the page

1. Open Reviews & Comments.
2. Enter your OpenAI API key, choose BMW G60, G70, or F70, and enter 1–10,000 comments.
3. Click **Collect & categorize**. This starts paid OpenAI requests.
4. When categorization finishes, validated rows are imported automatically and the page switches to the selected model with all markets and powertrains, making the new comments visible immediately.
5. Inspect collected, retained, discarded, and shortfall counts. Download **categorized.jsonl** or the complete **Import bundle**. **Retry import into reviews** remains available if an older completed run was not imported.

The collector uses OpenAI web search. Quotations are marked unverified model extraction, not independently verified Reddit comments. A count target can be missed. Categorization can discard some or all collected rows.

## Execution and files

Each run is isolated under `.local/reddit-runs/<job-id>/`:

- `collector/comments.jsonl`: unchanged collector export.
- `input.jsonl`: byte-for-byte copy supplied to the categorizer.
- `categorized.jsonl`: exactly `row_id`, `categorie`, `comment`, `date_displayed`, `sentiment_score` per retained row.
- `categorized.jsonl.discarded.jsonl`: the categorizer's discard-position/source-hash ledger.
- `manifest.json`: chosen vehicle, AI model versions, script hashes, file hashes, counts, category mapping, provenance and limitations.
- `import-bundle.zip`: the above handoff files plus collector report and saved API responses.

The worker invokes the current Python interpreter with argument arrays and `shell=False`. It calls:
`collect_reddit.py --topic "BMW <model>" --count <count> --out <run>/collector --model <collector-model>`,
then `categorize_comments.py <run>/input.jsonl <run>/categorized.jsonl --model <categorizer-model>`.

Defaults preserve the script choices: collector `gpt-5.5`, categorizer `gpt-4.1-mini`. Server operators may set `BMWPM_REDDIT_MODEL` and `BMWPM_CATEGORIZER_MODEL`. Values are saved with the job. Collector request limits remain its existing defaults. Collection times out after two hours; categorization after four hours. A requested count is not a guaranteed yield or dollar budget.

## Credential lifecycle

The password field is not backed by browser storage and is cleared immediately after submission. The API validates request bodies with fixed error messages, then passes a SecretStr directly to the in-memory worker. The key is excluded from persisted job inputs, results, audit events and command arguments. Each child receives its own `OPENAI_API_KEY` environment; the API process environment is unchanged. Subprocess stdout/stderr are discarded, and exception details are not returned. Calls target the official OpenAI endpoint.

This is the existing local demo application, not a multi-user authenticated service. Use HTTPS and authentication before remote deployment. A process restart loses pending credentials and marks jobs interrupted. Start a new run with a fresh key submission; generic job retry is blocked for this job type. Partial files remain on disk for inspection and are not offered as validated downloads.

## Validation and import

Collection exit 0 or 2 can continue if valid rows exist. Other exits stop the pipeline. A partial collection is reported with a shortfall. The categorizer must exit successfully and account for every input row through retained output or a validated discard record. IDs, text, dates, ordering, categories and finite sentiment values in [-100, 100] are checked. Only successful runs expose artifacts.

The five-field categorized file alone does not contain model or source provenance. Use its companion input and manifest, or the complete bundle. The page's import action consumes these saved files from the selected run; it is not the eight-file archive importer.

The adapter checks hashes again, imports one source-scoped feedback record per retained row automatically, preserves the complete raw collector record in evidence locations and source tags, and records AI category/sentiment as a pending category-level mapping. It does not infer an exact feature, market, powertrain, need type, approval or verified timestamp. All rows use origin `unknown`. Import, job completion, and the audit event commit together; a completed run with retained comments is therefore already visible. Repeated import of the same bundle is idempotent.

## Verification

`.venv/Scripts/python.exe -m pytest tests/test_reddit_pipeline.py tests/test_feedback.py -q -p no:cacheprovider`

The integration tests mock subprocess output and never call paid services. They cover model/count forwarding, exact file bridging, partial/empty collection, all-discarded output, invalid output, private-key handling, duplicate runs, downloads, import provenance, rollback and repeat import.
