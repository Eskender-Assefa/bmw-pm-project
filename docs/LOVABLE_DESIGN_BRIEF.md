# Lovable visual design brief

## Result

The [Premium Product Vision prototype](https://lovable.dev/projects/766e8a40-a0f2-4ab2-ac68-2309a4f8041d) was created in Lovable. Its compact navigation, blue interaction accents, and problem cards informed `src/app/premium-theme.css` in this repository. Both the Lovable prototype and working app now use a restrained dark theme with neutral charcoal surfaces, subtle borders, off-white text and selective BMW blue accents. The prototype uses sample data; this application remains the source of truth for requirements, scores, citations, decisions, and the hosted Sketchfab G60.

Use this prompt in Lovable to explore a new visual design. Lovable cannot import the existing `application_trial` repository, so treat its output as a design prototype. The maintained application remains the Next.js and Python project in this repository. Bring the chosen layout, styles, and components back into this repository after review.

## Prompt to paste into Lovable

Design a premium, BMW-inspired restrained dark interface for an existing product-management dashboard called **BMW Product Intelligence**. This is a visual redesign of an existing working application, not a new data product. Produce responsive desktop and mobile views with a coherent design system and realistic sample content. Do not invent API integrations, RAG answers, scoring methods, or approval behavior.

The current application has six persistent sidebar tabs: **Overview**, **Problems**, **3D model**, **Evidence library**, **Comparisons**, and **Decisions & audit**. Preserve all six. The selected BMW model is G60; model, market, powertrain, and evidence-origin filters are visible across views. Keep clear access to Import sources, Connect web evidence, and Export board deck.

Make the **Problems** view the strongest screen. Its ranked list needs a visible category code and name (C01–C10), specific problem title and description, source excerpts with original-file citations, review priority, demand percentage, impact band, status, filters, sort controls, and a Review & approve action. The selected problem should feel connected to the 3D model. Keep controls for **Problems only**, **Model only**, and **Merge tabs**, with a useful side-by-side layout for the merged view. Dense information should remain readable and scannable without hiding citations or scoring context.

The **3D model** view hosts the supplied 2024 BMW G60 Sketchfab viewer. Design a large model stage with room for labels and red priority highlights, transparent body control, Whole car/Cabin/Top/Side camera buttons, Baseline/After comparison, and a clear seat upholstery preview. Selected problems highlight their associated part or approximate region. Do not depict the hosted model as an editable CAD file; the seat concept changes finish while keeping the seat assembly in its original position. Keep Sketchfab attribution visible.

The Overview should show customer feedback, candidate requirements, mapping coverage, approved decisions, category opportunity, and evidence readiness with strong hierarchy. Evidence library, Comparisons, and Decisions & audit should look like parts of the same product, with readable tables, evidence references, and decision history.

Art direction: neutral charcoal surfaces, restrained BMW blue interaction accents, off-white text, and red reserved for urgent or selected vehicle components. Use excellent type hierarchy, consistent spacing, subtle borders and depth, crisp charts, and accessible contrast. Aim for a polished automotive planning tool, not a gaming HUD. Make the 3D viewer feel central. Avoid large empty hero areas, decorative car photos, fake data, and marketing-site styling. Keep keyboard focus, hover, selected, loading, and empty states coherent. On mobile, collapse the sidebar into navigation and stack the problem/model split without losing either view.

Deliver a working visual prototype and identify reusable colors, typography, spacing, components, and responsive rules. The implementation will be adapted into the existing Next.js frontend; its Python backend, database, data imports, and hosted Sketchfab integration must remain intact.

## Existing application locations

- Working source: `/home/soham/bmw-pm-editable-3d`
- GitHub: `https://github.com/so-0914/application_trial`
- Current local preview: `http://127.0.0.1:3002/`
- Frontend: `src/app/globals.css`, `src/components/`
- Backend: `backend/`
- Hosted model adapter: `src/components/sketchfab-g60.tsx`, `src/lib/sketchfab-controller.ts`

Lovable cannot access the local preview URL from its cloud service. Attach screenshots of the Overview, Problems, merged Problems + 3D, and mobile views in the Lovable project if you want visual continuity with the existing app. Do not upload the source spreadsheets, private database, or credentials for a styling exercise.
