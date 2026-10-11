# Editable local website

Run `npm run dev` in this folder, then open http://127.0.0.1:3001.
The backend runs on port 8001. Stop both with Ctrl+C.

The home page opens the connected Product Decision Studio, using the layout and styles of the old HTML prototype with live backend requirements, evidence, decisions, audit history and exports.

Edit `public/studio.html` for its page structure, `public/studio.css` for its appearance, and `public/studio.js` for its API connections. Refresh the browser after editing these static files. The original HTML is preserved unchanged at `public/legacy/BMW_Product_Decision_Prototype.html` and can be opened from the header. Its local prototype actions and simulated scores remain separate from backend decisions.

The complete React dashboard is retained at `/cockpit`. Edit `src/components/cockpit.tsx` for that dashboard, `src/components/workspaces.tsx` for its evidence library, `src/app/globals.css` for its styling, and `backend/` for API behavior. React edits reload automatically; restart after Python edits. All Python APIs, migrations, source documents, tests and database remain in this folder.

This copy has its own dependencies, source documents and SQLite database in `.local/cockpit.sqlite`. The original project remains in the parent folder.
