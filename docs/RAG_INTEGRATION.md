# Integrated document and review workflows

The implementation from `bmw-pm-project-reviews-and-RAG` is part of this editable
application. It uses the existing SQLite database, sources, evidence viewer,
ten categories, job queue and audit log. The Lovable interface, Problems / 3D
merge view, hosted G60, successor brief, USPs & cost and market trends remain.

- **Document intelligence**: upload PDF/XLSX/CSV/TXT/MD, index retained sources,
  search with local SQLite FTS5/BM25, review category/scope mappings, request
  structured extraction, and ask questions with validated source citations.
- **Reviews & Comments**: browse the selected feedback cohort with filters,
  pagination and original-source links. The supplied Reddit collection and
  categorisation scripts run through the existing persisted job queue and import
  validated output, preserving unknown provenance and category review status.
- **Problems → Search documents**: opens document search using the selected
  requirement's feature wording and model. The document workspace applies its
  own visible source/market/category filters; these do not redefine the feedback
  cohort or demand denominator.

The friend's retrieval, mapping, structured-answer validation, import and Reddit
pipeline logic are retained. UI styling, sidebar navigation, port handling and
job descriptions are integrated with this app. The standalone script dependency
pins use the same OpenAI SDK version as the app. The supplied `g60_research`
files remain available in the source tree; they are not silently imported as
verified customer records or counted in existing demand.

Migration `004_document_rag` adds chunks, FTS and immutable answer history. After
upgrading, choose **Index existing sources** once to populate document retrieval.
Supported retained PDFs and spreadsheets are indexed; the PowerPoint reference
remains available in Evidence library. No paid AI call occurs during startup,
import, indexing, navigation or local search. Answer generation and AI extraction
require the explicit checkbox and server `OPENAI_API_KEY`. Reddit collection uses
the key entered for that run and clears it from the form after submission.

RAG answers remain document interpretations. They do not auto-approve a requirement
or animate the car. The existing `/api/v1/vehicle-target` classifier and reviewed
design presets continue to control G60 highlighting and previews. This preserves
the friend's evidence workflow and the existing 3D decision flow.

Details: [Document RAG](document-rag.md), [Reddit pipeline](reddit-pipeline.md),
[G60 model](G60_3D.md). Tests mock external model calls; live provider availability
is separate from the local integration checks.

See [integration validation](RAG_INTEGRATION_VALIDATION.md) for the checks, retained
data, and current live-provider limitation.
