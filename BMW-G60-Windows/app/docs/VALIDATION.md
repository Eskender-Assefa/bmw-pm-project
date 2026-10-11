# Validation record — 10 October 2026

The application was validated locally on Windows, Python 3.12 and Node.js 24. The main reviewer database retains zero PM decisions; edits, approvals, tampering simulations and export tests ran against disposable backups.

## Reconciled imports

- All eight archive files retained with SHA-256 checksums, extraction version and source locators.
- F70: 2,128 distinct IDs / 4,076 tagged rows.
- G60: 4,000 distinct IDs / 5,005 tagged rows.
- G70: 4,000 distinct IDs / 4,690 tagged rows.
- Total: 10,128 distinct IDs / 13,771 tagged rows.
- G60 / US / all engines: 3,610 records (1,271 BEV, 2,017 ICE, 322 PHEV).
- Product catalogs: 1,108 structured candidates, all awaiting review; full source pages remain searchable and viewable.
- Studies: 185 means and 1,442 distribution values, with instruments kept separate.
- Sales: 36 observations, preserving combined G60/G68 aggregation.

An unchanged reimport added no Source, Feedback, Aspect or EvidenceRef duplicates. Representative G60 i5 eDrive40 page-4 candidates match 250 kW and EUR 70,900, explicitly DE-market and pending review.

## Executed checks

The complete backend suite passed **25 tests** in 42.57 seconds, including the local PDF-page preview and seeded web connector coverage. Each suite invocation now uses its own uniquely named database directory so concurrent checks cannot share test state. Coverage includes reconciliation, unchanged imports, mixed comments, duplicate wording, category-independent denominators, engine cohorts, excluded synthetic demand, observed web evidence isolation, web-source versioning, connector failure handling, study boundaries, critical ordering, cohort-specific decisions, stale-revision conflicts, rationale enforcement, append-only guards, privileged-event tamper detection, AI-reference validation, missing/stale replay, failed/interrupted jobs, human-labeling separation, FTS search, local-origin protection, scenario compatibility, immutable exports, long tables, fresh migrations, and rendered PDF-page responses.

`pnpm typecheck` and `pnpm build` passed. The optimized production build passed the Playwright browser flow in **17.4 seconds** (19.1 seconds including setup):

1. Open the default cohort.
2. Inspect an exact feedback row and original source link.
3. Replay a genuine matching AI result without an API key request.
4. Edit the customer need and create revision 2.
5. Approve revision 2 with High impact and a rehearsal rationale.
6. Verify audit integrity.
7. Export and download the deck; validate the frozen snapshot's revised title, band, numerator/denominator and approval count.

All non-loopback browser requests were blocked for the entire test; none were attempted. This rehearses operation without external browser networking. It does not change the operating system's network configuration. Live AI was not invoked in that rehearsal.

## Live AI and replay provenance

A real `gpt-4.1-mini-2025-04-14` Responses API call generated the delivered replay on **2026-10-10 at 19:39:38 UTC**. Eight supplied touchscreen-related feedback records were sampled in stable evidence-ID order. Inputs, outputs, versions, timestamp and integrity hash are stored in `fixtures/replays/3ab8c6744ae856b8855c7750417faf8504a89802067a1798daec1fa2a77da413.json`.

One earlier attempt failed to connect from the sandbox. Another response failed evidence-reference validation. Both remain failed jobs; neither became a usable analysis. The final response passed exact quote/reference validation. The fixture successfully loaded from disk with the API key removed and became unavailable after the requirement revision changed.

## Visual verification

The dashboard was inspected at compact and desktop widths. Source records, typed product facts, requirement review, comparisons and the decision/export flow were inspected. The in-app browser did not reliably display its native embedded PDF viewer, so the application now renders the exact original PDF page locally as a cached PNG while retaining the original file link.

The 15-slide rehearsal deck was rendered to PNG using the bundled PowerPoint renderer. All slides were inspected in a contact sheet; changed requirement and comparison slides were also inspected at full size. No clipping or overlap was found. The approved revised title, source rows, model/market context, unknown inputs, scenario units, VAT basis and appendix origin labels remain present. Long evidence and source registers paginate instead of shrinking body text.

Local QA artifacts (excluded from source control): `.local/qa/BMW-G60-rehearsal.pptx`, its `-snapshot.json`, slide PNGs in `.local/qa/final-deck`, and `.local/qa/import-reconciliation.json`. The sample deck contains an **automated rehearsal decision**, not a real PM approval. Playwright reports and download screenshots are under `playwright-report` and `test-results`.

## Quality limits that remain visible

Mapping accuracy is **not measured**: calibration 0/40 human-labeled; held out 0/60. The prepared benchmark reports unavailable accuracy and disallows automatic promotion. Dictionary suggestions and AI interpretations remain proposals.

PDF normalization is intentionally conservative; candidates and ambiguous availability cells await human review, and unnormalized text remains accessible on its original page. No claim of complete verified specification extraction is made. Customer origin, feedback dates, sample sizes, engineering feasibility, costs and sales causality remain unknown. The audit chain has no external integrity anchor or enterprise immutable-storage guarantee.
