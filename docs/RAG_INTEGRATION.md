# RAG integration handoff — proposed, not implemented

The RAG engine is being developed separately. No retrieval engine, vector store or indexing job is implemented here. The Problems tab displays imported source citations and a RAG connection-pending label; the 3D model tab can merge alongside it. The part classifier is a separate, user-authorized model call.

Connect the engine through a future server-side adapter in `backend/`; the React UI should continue talking to this application's same-origin `/api/v1` API. Whether the adapter imports a Python module or calls an external HTTP service can be decided with the engine team. Keep service credentials in the server environment.

Existing integration inputs are the selected `Cohort` (`model`, `country`, `powertrain`, `origin`), requirement ID/revision when present, original source IDs/checksums and evidence IDs/locators. Read APIs already expose sources, evidence, requirement detail and evidence search. General evidence search is a source explorer, not cohort-filtered retrieval; the adapter must apply the requested cohort before assembling context.

Proposed responses contain an answer, citations with existing evidence/source IDs and exact locators, uncertainties, and an optional proposed design concept. Limit design concepts to supported component IDs and the named `baseline`, `screen`, `vents`, or `seats` design presets in `src/lib/vehicle-priority.ts`. Do not execute generated code, arbitrary geometry scripts, or arbitrary URLs from engine output.

Resolve citations against retained source records before displaying them. Keep generated interpretations separate from measured demand, PM impact bands and approved decisions. Require the existing PM review/revision flow to adopt changed requirement text. A proposed design concept may drive the preview controls after explicit selection, but should never silently save a decision or modify source evidence.

Extension points: `ProblemWorkspace` for the problem list and source citations; `RequirementDrawer` for cited interpretation; `VehiclePreview` for the selected validated concept; existing `EvidenceModal` for original citations. Final endpoint and payload shapes remain to be agreed with the engine team.

The separate `/api/v1/vehicle-target` classifier now supplies constrained part IDs and an optional supported design preset on row selection, with user-authorized live AI enabled by default, an off switch, and a labelled local fallback. The future RAG engine can supply the same validated contract. It does not replace the ten source categories or estimate benefit/ROI.

The ranking response now includes `evidence_samples[].source = {id, filename, kind}` alongside the existing evidence ID, quote and locator. A future RAG adapter should resolve retrieved citations to this same source/evidence provenance, return retrieval status explicitly, and never relabel current imported snippets as RAG-generated answers. Screen and vent presets use projected surfaces on the hosted Sketchfab model, while seats use an assembly transform; see `sketchfab-controller.ts` for verified mesh capabilities.
