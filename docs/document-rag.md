# Document Intelligence (RAG v1)

This is an incremental addition to the existing cockpit, not a replacement database.
It uses the same SQLite database, ten C01-C10 categories, evidence IDs, source files,
job queue and append-only audit. Reddit collection/import is also integrated; see [Reddit pipeline](reddit-pipeline.md).

## Start or Upgrade

In this editable copy the active instance uses web port **3002** and API port
**8002**. Launch it with `BMWPM_WEB_PORT=3002 BMWPM_API_PORT=8002 npm run dev`.
The defaults below describe the supplied implementation. See
[RAG integration](RAG_INTEGRATION.md) for how it fits the existing dashboard.

Back up `.local/cockpit.sqlite` with SQLite's backup API before migrating an existing
workspace. Stop active jobs first; do not copy a database while it has open writes.

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
corepack pnpm dev
```

Restart the backend after updating Python code. Do not launch a second server on
ports 3000 or 8000. Open http://127.0.0.1:3000 and choose **Document intelligence**.
The existing eight-file ZIP importer is unchanged.

If another checkout/server already owns those ports, the launcher accepts
`BMWPM_API_PORT=8001` and `BMWPM_WEB_PORT=3001`. Set `BMWPM_VERIFY_BUILD=1` for a
separate Next.js cache when keeping an existing frontend running. Both instances
use the same `.local` database unless explicitly configured otherwise; never run
imports or migrations concurrently in two server instances.

1. **Index existing sources** adds searchable passages from already imported PDF,
   Excel and text evidence. It does not re-import or increase customer counts.
2. **Add documents** accepts up to ten PDF, XLSX, CSV, TXT or MD files per batch.
   There is a 20 MB per-file limit and 40 MB batch limit. Legacy XLS needs conversion.
3. Supply the actual model and market for the batch, or leave them unknown. An XLSX
   or CSV can use a `Model`, `vehicle_model` or `model_code` column to identify each
   row. A conflicting batch model fails that file instead of changing its identity.
4. **Category mappings** is the default document view. Choose a document source to
   see all ten categories, including those with no mapped evidence. Switching
   sources clears stale model/category/search filters. A single-file import opens
   its summary automatically, without a second import or an AI call.
5. The coverage table counts all matching passages, not just the visible page.
   Pending/reviewed/rejected counts describe mapping rows; one passage may have
   multiple features and categories. The category selector filters the detail rows
   while the coverage table retains all ten categories. Other document filters
   apply to both tables, separately from the customer cohort filters.
6. Detail rows show category/scope, feature, value/unit, car variant, source page
   or spreadsheet location, quoted evidence, extraction method and passage review
   status. Legacy keyword hints display **Not extracted**, not fabricated values.
   Empty categories mean no current mapping, not that a vehicle lacks a feature.
7. Review a passage, correct/add its category and scope aspects, preserve an exact
   source quote, and accept/reject it with a rationale. This is a mapping review,
   not approval of a specification, requirement, priority or production change.

## Local Retrieval and Opt-in AI

Extraction, deduplication, chunking, initial lexical category hints and search run
locally, with no API calls. Retrieval is **SQLite FTS5 BM25**, not vector semantic
search. Queries use token/prefix matching. Paraphrases and cross-language queries
can miss evidence; a no-match result never proves a feature is absent.

For semantic category suggestions and structured feature extraction, select up to
12 pending passages and explicitly enable paid AI calls, then use **Extract &
categorise**. Each passage can propose up to 20 feature/aspect rows, including
multiple rows within one category for different variants. Value, unit and variant
must each occur verbatim in the row's supporting quote; uncertain associations in
interleaved PDF tables must remain null. The feature label may be normalized.
For a grounded answer, ask a question and enable paid calls.
The answer retrieves up to eight distinct matching passages and passes those,
their source metadata, and the question to the configured OpenAI model. It does not
send the entire corpus. The server uses `OPENAI_API_KEY` and `OPENAI_MODEL` (or the
existing default model); keys never go to the frontend. Existing replay analysis
for individual requirements remains unchanged. RAG has no fabricated replay mode.

The adapter uses the Responses API with `store=False` and structured output:
https://developers.openai.com/api/docs/guides/structured-outputs

The UI's AI confirmation permits a paid request and disclosure of those selected
passages to the provider. No live calls are made by import, indexing or page loads.
Tests replace the provider with deterministic fake responses, not real requests.
No embeddings service, hosted vector store or additional dependency is required.

## Data and Safety Contract

- `sources` and `evidence`: original checksum, original file, page/sheet/row/line,
  explicit model, market and origin. Generic imports use `kind=document` and do
  not enter `feedback`, existing demand denominators or auto-created requirements.
- `rag_chunks`: exact 1,800-character windows with 180-character overlap, source
  and evidence foreign keys, text offsets, model, version, category/scope aspects,
  review status, revision and method. Identical repeated tag text in one source
  and model has one representative citation. Passage counts are not customer counts.
  Assignment JSON now optionally includes `feature`, `value`, `unit`, `variant`.
  Old assignments are read with null defaults; no data migration or re-index is
  needed. Prompt version `document-rag-v2` records the extraction contract.
- `POST /api/v1/rag/mappings`: read-only, paginated mapping details plus full
  ten-category aggregates, applying source/model/origin/market/search/review/scope
  filters before aggregation. Category and scope apply to the same aspect. This
  endpoint makes no AI calls and never changes customer demand or PM decisions.
- `rag_fts`: local lexical retrieval index. Metadata filters apply before ranking
  and pagination. Category and scope must match the same aspect.
- `rag_runs`: immutable question/classification inputs, retrieved citation snapshot,
  model/prompt version and validated output. Saved answers can be reopened.
- Scope is separate from category: `fixed`, `variable`, `hypothetical`, `unknown`.
  A scope proposal is not a verified fact. Ambiguous material stays pending.
- Content and filenames are untrusted. Responses have no tools. Output IDs and
  exact quotes are validated against supplied passages; malformed responses,
  missing IDs, refusals, stale evidence and unavailable providers fail visibly.
  Exact quotation does not prove the model's interpretation is correct. A human
  still reviews meaning, table columns, footnotes, variants and jurisdiction.
- Human-reviewed or rejected mappings cannot be overwritten by AI classification.
  Concurrent review conflicts use revisions; changes are audited.
- Rejected passages are excluded from generated answers. Unknown and synthetic
  origins stay explicit. Cited German catalogue text is not US availability proof.
- New editions with different bytes are distinct sources. Identical bytes are
  skipped, even if renamed; existing metadata is retained. Source retirement and
  metadata correction UI are not yet included.
- The service remains a local-only, single-user hackathon app. It is not hardened
  for public uploads, multi-user auth, malware analysis or tenant isolation.

## Extraction Limits

PDFs: at most 500 pages, selectable text only; blank/scanned pages are reported.
No OCR, image interpretation or automatic PDF table-cell reconstruction. XLSX:
cached formula results only, no calculation engine; header row defaults to one.
CSV: UTF-8, comma-separated. Text/Markdown: UTF-8, line-addressed. A file is limited
to 50,000 records, a sheet to 200 columns and a record to 200,000 characters. XLSX
expanded content is bounded at 100 MB. Limits fail rather than silently truncate.
Imports use per-file transactions; partial failures are shown per file in the job
result. Uploaded originals remain under `.local/uploads` for citations and retries.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rag.py tests/test_contract.py -q
corepack pnpm typecheck
$env:BMWPM_VERIFY_BUILD='1'
corepack pnpm build
Remove-Item Env:BMWPM_VERIFY_BUILD
```

Tests use disposable SQLite backups; they never modify the user's database.
They exercise extraction, import idempotence, filters, citations, stale concurrent
reviews, no-provider fallback, immutable history, uploads, full-result mapping
counts, multi-variant feature rows, legacy defaults and original customer counts.
Model classification accuracy and semantic answer correctness have not
been measured on a human-labeled RAG benchmark.

The supplied project's recorded check on 2026-10-11 (before integration): 50 tests, type checking and the production build passed.
The ten-category overview, source-page preview and responsive mapping rows were
checked in the browser. The user-authorized BMW 5er live extraction did not
complete: the first request failed to connect; an explicitly approved retry
reached OpenAI but returned HTTP 429. No AI feature values were saved and no PM
decisions changed. Existing rows remain lexical suggestions pending review.

## Next Phase

The Reddit adapter is now supplied separately in the same application; see
[Reddit pipeline](reddit-pipeline.md). Its output remains unverified model
extraction, with original URLs and deduplication metadata retained. Keep account/privacy permissions and source terms outside the model.
Semantic embeddings can later supplement BM25 with a versioned vector index and
measured retrieval tests. Production scale would require job workers, upload
quotas, access controls and a database migration rather than unlimited local scans.
