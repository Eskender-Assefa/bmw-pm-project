# Editable local website

Run `npm run dev` in this folder, then open http://127.0.0.1:3001.
The backend runs on port 8001. Stop both with Ctrl+C.

The home page opens the sidebar cockpit. Its five dashboard tabs are unchanged. The G60 3D preview is embedded in Overview and requirement review; it is not an extra tab.

The combined HTML interface remains available at `/studio.html`. Edit `public/studio.html` for its page structure, `public/studio.css` for its appearance, and `public/studio.js` for its API connections. Refresh the browser after editing these static files. The original HTML is preserved unchanged at `public/legacy/BMW_Product_Decision_Prototype.html` and can be opened at `/legacy/BMW_Product_Decision_Prototype.html`. Its local prototype actions and simulated scores remain separate from backend decisions.

The React dashboard is also available at `/cockpit`. Edit `src/components/cockpit.tsx` for that dashboard, `src/components/workspaces.tsx` for its evidence library, `src/app/globals.css` for its styling, and `backend/` for API behavior. React edits reload automatically; restart after Python edits. All Python APIs, migrations, source documents, tests and database remain in this folder.

The 3D controls are in `src/components/vehicle-preview.tsx`, the Three.js scene in `src/components/vehicle-scene.tsx`, and editable geometry in `src/lib/g60-geometry.ts`. Feature mappings and colour rules are in `src/lib/vehicle-priority.ts`. Try buttons are temporary visual previews. The approval dialog can save a chosen design with the PM decision; accepted designs restore after reload. See `docs/G60_3D.md` and `docs/RAG_INTEGRATION.md` for extension points.

This copy has its own dependencies, source documents and SQLite database in `.local/cockpit.sqlite`. The original project remains in the parent folder.
