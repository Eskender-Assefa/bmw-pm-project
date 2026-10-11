# Editable local website

The working folder is `/home/soham/bmw-pm-editable-3d`. The backup at
`/home/soham/bmw-pm-project-master/editable-copy` is separate.

Run `BMWPM_WEB_PORT=3002 BMWPM_API_PORT=8002 npm run dev` here, then open
http://127.0.0.1:3002. Stop both processes with Ctrl+C. The launcher defaults to
3001/8001 when those environment overrides are absent.

The home page and `/cockpit` open the same sidebar application. Problems and
3D model can merge side by side. Successor brief, USPs & cost and Market trends
are the three handover panels. Document intelligence and Reviews & Comments
include the supplied RAG, review and Reddit collection workflows.

## Source map

- `src/components/cockpit.tsx`: navigation, cohort and shared job controls.
- `src/app/premium-theme.css`: the Lovable-based restrained dark styling and roundel layout.
- `src/app/rag-theme.css`: matching styles for the imported RAG/reviews panels.
- `src/components/problem-workspace.tsx`: ranked problems, scores, sources,
  document-search links and the merged 3D workspace.
- `src/components/vehicle-preview.tsx`, `sketchfab-g60.tsx`, and
  `src/lib/sketchfab-controller.ts`: hosted G60 selection, highlights and previews.
  `src/lib/vehicle-priority.ts` contains component mapping and presets.
- `src/components/document-rag.tsx` and `document-mappings.tsx`: document import,
  search, mapping review and cited answers; `backend/documents.py`, `rag.py`,
  `rag_routes.py`, `rag_schemas.py` implement the supplied engine.
- `src/components/reviews-comments.tsx` and `reddit-collection.tsx`: comment
  browser and collection form; `backend/feedback.py`, `reddit_pipeline.py`,
  `reddit_routes.py`, `reddit_collector/` and `Categorized-Scrapped-Data/` implement
  the supplied pipeline.
- `backend/`: Python API, scoring, requirement decisions and export.
- `migrations/`: schema history, including `004_document_rag`.

React edits reload automatically; restart after Python edits. The copy has its
own source documents and SQLite database in `.local/cockpit.sqlite`. Dependencies,
credentials, database state and generated artifacts stay outside Git. Back up the
SQLite database with its backup API before migrations.

The hosted G60 requires internet/WebGL. Seat previews change upholstery while
preserving the seat position. The previous procedural Three.js implementation
remains in source for reference. See [G60 notes](docs/G60_3D.md) and
[RAG integration](docs/RAG_INTEGRATION.md).

The combined HTML remains at `/studio.html` (`public/studio.html`, `studio.css`,
`studio.js`). The original prototype is retained under `public/legacy/`. Its
simulated scores and local actions remain separate from backend decisions.
