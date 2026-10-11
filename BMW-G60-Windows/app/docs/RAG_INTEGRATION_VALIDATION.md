# RAG integration validation — 11 October 2026

Target: `/home/soham/bmw-pm-editable-3d`, integrating
`/home/soham/bmw-pm-project-reviews-and-RAG`. The original project and its
`editable-copy` backup were not edited. The active instance uses web port 3002
and API port 8002.

## Checks

- Full backend suite after migration: **198 passed, 1 skipped, 3 failed**.
  All imported RAG, feedback and Reddit pipeline tests pass. The three failures
  predate this integration and require the full original dataset:
  `test_import_counts_and_original_rows` expects F70/G70 alongside G60;
  `test_mixed_comments_and_identical_text_ids` expects duplicate-text examples
  absent from this subset; `test_studies_sales_and_catalog_retain_boundaries`
  requires study/sales files absent from this copy. They were not weakened.
- Standalone collector: **22 tests + 7 subtests passed**. Categorizer/evaluation:
  **32 tests + 60 subtests passed**, using the app's installed OpenAI SDK 3.28.0.
- `npm run typecheck`, `BMWPM_VERIFY_BUILD=1 npm run build`, and
  `python -m pip check` passed.
- `node tests/sketchfab-controller.mjs` passed mesh/material restoration, original
  seat transforms, new seat appearance, projections and selection/error recovery.
- HTTP checks through the frontend returned 200 for existing overview, successor,
  USP and trends routes plus RAG, feedback and Reddit routes. A document search
  with the 3002 Origin header succeeded through the Next.js proxy.
- Browser checks: both new dark panels, document/source filters, local search,
  original PDF page and spreadsheet citations, AI consent gating, comment search
  and pagination, and Problems → Search documents with G60/feature context.
  The hosted model rendered with a visible engine/power region highlight.

## Migration and retained state

A SQLite backup was saved before `004_document_rag` under
`.local/backups/before-rag-20261011T055719Z.sqlite`. Indexing produced **4,182
passages from three existing supported sources**, with 5,095 initial mapping
rows. These are pending lexical hints, not human-verified feature extraction.
The keynote PPTX remains in the original Evidence library; the supplied engine
indexes PDF, XLSX, CSV, TXT and MD.

Every row in the original sources, evidence, feedback, aspects, facts,
requirements, revisions, decisions, analysis, priority and export tables was
compared with the backup and remained identical. This includes **4,000 G60
feedback records, 216 requirements and the existing decision**. The US cohort
still contains 3,610 records. The audit chain verifies after indexing.

## Live-provider limit

RAG/Reddit tests use fake providers or subprocesses. No live RAG answer,
classification or Reddit collection was submitted. The existing automatic 3D
part-identification request reported that OpenAI rejected the configured key;
local part matching remained active. A working server `OPENAI_API_KEY` is needed
for live RAG generation/extraction; Reddit collection accepts a key per run.
A configured-key boolean only reports presence, not validity or available quota.
