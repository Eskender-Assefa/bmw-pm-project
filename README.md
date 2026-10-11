# BMW Product Manager Cockpit

## Application Trial — combined local website

## Portable Windows package

The Windows x64 ZIP includes a native `Start BMW.exe` launcher, bundled Python dependencies, a prebuilt dashboard and a database/document snapshot. Extract the entire ZIP, then double-click the launcher. See [Windows instructions](docs/WINDOWS_PORTABLE.md).

## Handover panels

The sidebar also includes **Successor brief**, **USPs & cost**, and **Market trends** from `bmw-handover.zip`. Their FastAPI routes are `/api/v1/successor`, `/api/v1/usp`, and `/api/v1/trends`; Keep and Lead proposal reviews use `/api/v1/successor/{id}/review` and the existing audit trail. The trends register is `fixtures/market-trends.json`. Cost is an adjustable estimate, and trend summaries remain pending source review. The RAG engine from `bmw-pm-project-reviews-and-RAG` is now integrated alongside these panels. The existing Problems, 3D model, merged view, evidence, comparison, decision, and Lovable-styled interface remain available.


This editable copy has eleven sidebar tabs. Start with `npm run dev` and open **http://127.0.0.1:3001** (API: **8001**). The current local instance uses **3002/8002** via `BMWPM_WEB_PORT=3002 BMWPM_API_PORT=8002 npm run dev` to avoid the backup's ports. Problems shows detailed needs, original source citations and scores. **Merge tabs** connects it side by side with the hosted BMW G60 model; the selection and filters persist between the two views. The model itself receives red part highlights, transparency, screen/vent surface concepts and seat upholstery previews through Sketchfab's supported API. Approved presets persist with PM decisions. Live AI part identification is authorized, enabled by default and has a visible local fallback. Document intelligence and Reviews & Comments now integrate the supplied RAG and Reddit pipeline. See [the integration notes](docs/RAG_INTEGRATION.md) and [the model notes](docs/G60_3D.md). The connected HTML Studio remains at `/studio.html`, and the original prototype remains at `/legacy/BMW_Product_Decision_Prototype.html`.

For a fresh Linux checkout (Node.js 20.9+ and Python required):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
corepack pnpm@10 install --frozen-lockfile
.venv/bin/python -m backend.cli migrate
.venv/bin/python -m backend.cli import-files G60_OptionList.PDF BMW_G60_Scopes_and_Data.pdf '261010_BMW_Product_Management_Key_Note(1).pptx' G60_feedback_hackathon.xlsx
npm run dev
```

See [EDITING.md](EDITING.md) for the source-file map. Dependencies, local database decisions, exports and credentials are excluded from Git; the supplied source documents are included so a fresh clone can import the G60 data. Python 3.14 is used by this local copy; the original project was tested with Python 3.12.

The notes below describe the original full dataset. This copy contains the G60 subset, and its launcher uses ports 3001/8001 instead of 3000/8000.

A local G60-led hackathon application for exploring supplied evidence, reviewing customer requirements, recording PM decisions and exporting an executive PowerPoint. F70 and G70 are imported alongside G60. The interface includes Overview, Problems, 3D model, Successor brief, USPs & cost, Market trends, Evidence library, Document intelligence, Reviews & Comments, Comparisons, and Decisions & audit.

## Run the prepared workspace

```powershell
pnpm dev
```

Open **http://127.0.0.1:3000**. Both processes bind only to `127.0.0.1`; the API runs on port 8000. Stop them with Ctrl+C. The local database and source files are already imported in `.local`. No API key or internet connection is needed to explore, review, export, or use the supplied matching replay.

For the optimized demonstration build, run `pnpm build` once, then `pnpm serve`. This starts both services without development tooling in the interface.

## Fresh setup

Requires Python 3.12, Node.js 20.9 or newer, and pnpm. Tested here with Python 3.12 and Node.js 24. Dependencies are locked for the frontend and pinned for the main backend packages.

```powershell
./scripts/setup.ps1 -Archive 'C:\path\to\BMW-Data-20261010T183823Z-1-001.zip'
pnpm dev
```

Equivalent manual steps:

```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
pnpm install --frozen-lockfile
./.venv/Scripts/python.exe -m backend.cli migrate
./.venv/Scripts/python.exe -m backend.cli import 'C:\path\to\BMW-Data-20261010T183823Z-1-001.zip'
./.venv/Scripts/python.exe -m backend.cli openapi
pnpm generate:types
pnpm dev
```

On macOS/Linux, create the environment with `python3.12 -m venv .venv` and use `.venv/bin/python`. The Node launcher handles either environment layout. `BMWPM_PYTHON` can select another Python executable.

The web **Import sources** action also accepts the archive's full local path. Unchanged checksums are skipped. An altered file with an existing filename is rejected rather than silently replacing evidence; handling a new source edition requires an explicit import migration.

## Demo behavior and data boundaries

For the individual G60 files supplied with this workspace, import them directly:

```bash
.venv/bin/python -m backend.cli import-files G60_OptionList.PDF BMW_G60_Scopes_and_Data.pdf '261010_BMW_Product_Management_Key_Note(1).pptx' G60_feedback_hackathon.xlsx
```

This subset populates G60 feedback and equipment. The scopes PDF and keynote slide text appear as searchable Project references in the Evidence library; they do not count as customer feedback or verified equipment facts. Original documents are retained. Reimporting identical files skips them. Other model feedback, sales and customer studies require their corresponding source files.

| Imported feedback | Tagged spreadsheet rows | Distinct source-scoped IDs |
|---|---:|---:|
| F70 | 4,076 | 2,128 |
| G60 | 5,005 | 4,000 |
| G70 | 4,690 | 4,000 |
| Total | 13,771 | 10,128 |

The default G60 / US / all-powertrain cohort contains **3,610** eligible records. The remaining model records are available through the cohort filters. A feedback ID is a record, not a verified unique person. Original tags and spreadsheet rows are retained. Identical text with different IDs is flagged but not merged.

The Evidence library is a source explorer: it uses the selected model, or an explicitly selected source file, and shows all supplied source markets and powertrains, with this scope stated above its records. Overview, Requirements and decision exports use the full selected feedback cohort. Catalog pages have a local PNG preview as well as the retained original PDF link.

## Web evidence connectors

**Connect web evidence** imports seeded public webpages or forum threads. The connector fetches only the URLs entered by the PM, checks `robots.txt`, saves the exact static HTML snapshot, extracts readable qualitative text blocks, and stores them as observed evidence with URL, retrieval metadata, checksum and block location. It does not crawl links, log in, use cookies, render JavaScript, or access private/local network addresses.

Scraped evidence is labeled **Observed web evidence**. It appears in Evidence and Mapping Review first. The default dashboard remains governed by the supplied hackathon data (`origin=unknown`); web evidence contributes to requirements and demand only when the Evidence origin filter is changed to **Observed** or **All**. Web-derived feature mappings are lightweight keyword suggestions and require PM review.

The three German equipment PDFs retain every page and 1,108 structured extraction candidates, including specifications, prices and option availability. These candidates **require review** against the original page. All page text is searchable even where a table cannot be safely normalized. Unknown cells remain unknown; this is a reviewable import, not a claim of complete verified equipment coverage. Prices preserve German VAT and package conditions. German equipment cannot establish US availability.

Study means (185 values) and rating distributions (1,442 values) use separate instruments. Their sample sizes and cross-instrument conversions remain unknown. The 36 sales observations retain their supplied aggregation, including combined G60/G68 totals and explicitly unverified future 2030 values.

Demand is distinct unmet-need records divided by all eligible records in the same cohort. Category and display-order changes never alter the denominator. Likes remain strengths/conflicting observations. Review order is critical-review flags, PM impact band, then descending demand. Flags indicate a need for expert review, not confirmed severity or defects. Unreviewed impact is Unscored. Velocity, engineering effort, ROI and sales causality are unavailable.

## AI and saved replay

The default is **Saved replay**. A genuine OpenAI result is supplied for:

- G60 / US / all powertrains / supplied-unverified origin.
- **Touch screen, operation**, revision 1, original template text and original mappings.
- Model `gpt-4.1-mini-2025-04-14`, prompt `requirements-v1.1`, pipeline `evidence-v1.0`.
- Original generation: **2026-10-10 19:39:38 UTC**.

Find that requirement and click **Replay analysis**. It uses eight distinct supporting records selected by stable evidence ID. This is a small, explicitly nonrepresentative interpretation sample; demand always comes from the full SQL cohort. Draft interpretations include quoted aspects, feedback type, sentiment, proposed criteria and uncertainties. They do not silently change feature mappings or requirements. Adopting a draft creates a PM-attributed revision.

Portable fixture JSON is in `fixtures/replays`. It contains the exact inputs, output, original timestamp, model and pipeline versions, and an integrity hash. The code validates referenced evidence IDs and exact quoted spans. Changed requirement text, revision, evidence mapping, cohort, model or pipeline invalidates the replay. Other requirements need their own saved live run; missing replay is a visible, recoverable state.

To enable explicit live actions, set `OPENAI_API_KEY` in the **server process environment**, restart, then select **Live AI** and press **Run live analysis**. `OPENAI_MODEL` is optional. `.env.example` documents the settings; this application does not automatically load `.env` files. Never put a key in frontend variables or commit it. Live analysis sends up to eight supplied excerpts to OpenAI with `store=False`. Connection failures, refusals and invalid citations leave a failed job and do not create an invented result.

For an explicit command-line live run, `./.venv/Scripts/python.exe -m scripts.seed_replay` generates the touchscreen replay. This makes a real API request and may incur API usage. Normal startup makes no AI request.

Decisions & audit → Analysis & jobs preserves recent outcomes across restart, including failed requests and explicit retry controls. Failed live requests are never silently replaced with a fixture.

## Decisions, audit and exports

The reviewer is visibly identified as **Demo PM**, a demonstration identity without authentication. Approve, edit, reject, postpone and impact review write a decision and hash-linked audit event in one SQLite transaction. Rejection, postponement, edits and band changes require a rationale. Optimistic revision checks reject stale edits. Editing an approved requirement creates a new Proposed / Unscored revision; old decisions remain intact. Decisions and impact bands apply to the exact cohort reviewed.

The database blocks application updates/deletes to decision, revision, analysis, priority-snapshot, export and audit records. The audit checker detects modified events. This is application-level integrity, not an independently anchored or enterprise-immutable log; a privileged attacker can replace the database or truncate an unanchored tail.

**Export board deck** freezes the current cohort, approved revisions, rationales, demand, citations, source checksums and optional scenario. PPTX and downloadable snapshot JSON remain available under Decisions & audit → Executive exports. Empty approval sets produce an explicit empty-state deck. Long content is paginated at readable font sizes.

The comparison fixture uses hypothetical DE / BEV Mercedes and BYD variants. It contributes no demand or priority. A BMW comparison requires one reviewed fact with matching market, variant, units and feature definition. Otherwise the cell reads **Not comparable**. Scenario material appears only in the deck appendix.

## Verification

```powershell
./.venv/Scripts/python.exe -m pytest -q
pnpm typecheck
pnpm build
```

The integration suite requires the imported `.local/cockpit.sqlite` seed. Every test works on a disposable SQLite backup; it does not edit the reviewer's data. Set `BMWPM_TEST_SEED` or `BMWPM_SOURCE_ARCHIVE` when using another location. An unchanged-archive test is skipped only when the archive cannot be found.

For the complete browser rehearsal, stop the normal app and create a new named copy:

```powershell
./.venv/Scripts/python.exe -m scripts.prepare_e2e --name rehearsal-1
$env:BMWPM_DATA_DIR=Join-Path (Get-Location) '.local/rehearsal-1'
$env:BMWPM_REHEARSAL='1'
pnpm dev
```

In a second terminal run `pnpm test:e2e`. It uses installed Microsoft Edge on Windows, or Playwright Chromium elsewhere. Set `PLAYWRIGHT_CHANNEL=chrome` for installed Chrome. The test refuses to mutate an app without rehearsal mode. It blocks all non-loopback browser requests, inspects evidence, replays the saved AI result, edits, approves and downloads a frozen deck. Use a **new copy for each run**, because the test intentionally creates an enduring revision and decision. Close the rehearsal server, clear `BMWPM_DATA_DIR` and `BMWPM_REHEARSAL`, then run `pnpm dev` to return to the main database.

See `docs/VALIDATION.md` for recorded verification and `docs/DEMO.md` for the demonstration script.

## Human evaluation

Evidence library → Human evaluation contains 100 stratified, text-deduplicated records: 40 calibration and 60 held out. No labels have been fabricated. Category-set accuracy stays unavailable until a reviewer labels records; results are reported separately for both splits. Automatic mapping promotion is disabled. Export the set with `python -m backend.cli evaluation`. The held-out set must remain outside prompt/taxonomy tuning; use the calibration subset for that work.

## Implementation map

- `backend/ingestion.py`: checksum-based adapters, source retention, spreadsheet deduplication and PDF geometry extraction.
- `backend/taxonomy.py`: versioned C01–C10 tag dictionary and review flags.
- `backend/services.py`: cohort demand, requirement revisions and atomic decisions.
- `backend/connectors.py`: seeded public web connector, static HTML snapshots, robots checks and observed qualitative evidence import.
- `backend/analysis.py`: structured Responses API, quote/reference validation and exact-input replay.
- `backend/jobs.py`: one persisted queue with one worker. Restarted unfinished jobs become Interrupted and require an explicit retry.
- `backend/exporter.py`: editable python-pptx decks from frozen snapshots.
- `migrations/versions`: initial schema, FTS/integrity triggers, and critical-flag scope migration.
- `src/components`: Next.js client interface, Radix/shadcn-style accessible controls and Tailwind/CSS.
- `src/lib/api-types.ts`: generated from FastAPI's OpenAPI schema, never manually edited.
- `fixtures`: separately labeled competitor assumptions and genuine replay provenance.

API documentation: http://127.0.0.1:8000/docs. All application endpoints are under `/api/v1`. `BMWPM_DATA_DIR` selects another local data folder; `BMWPM_DATABASE_URL` overrides the SQLite URL. Back up the database using SQLite's backup facility while running, or copy the complete data directory after stopping the app. Original source paths are absolute; moving the workspace requires reimporting sources into a fresh database or updating paths through a deliberate migration.

Broad crawlers, JavaScript-rendered evidence capture, comprehensive reviewed PDF normalization, calibrated automatic mapping, authenticated sharing, PostgreSQL and production operations remain future work.
