# Frontend redesign implementation handoff

**Status:** written on 4 November 2026 before the local redesign. See the [implementation review](FRONTEND_REDESIGN_IMPLEMENTATION_2026-11-05.md) for what was completed and checked afterward.

## Objective

Bring the strongest visual ideas from the user-supplied **Image Origin Studio Redesign.zip** into the existing React/TypeScript app. Make Analyze, Gallery, and History clearer and more polished at phone, tablet, and desktop widths while preserving their real behavior, source evidence, and privacy rules. Work in this repository; treat the Figma Make export as a visual prototype, not replacement application code.

The Figma export suggests a useful editorial direction: warm paper background, restrained teal, generous spacing, strong headings, a clear three-step Analyze setup, a horizontal image queue, separate result cards, a guess-then-reveal Gallery, and a welcoming signed-out History view. Its standalone implementation has a TypeScript syntax error, simulated timers, hard-coded results and metadata, mock sign-in/History, nonfunctional export controls, and eight substituted camera-photo gallery items. Do not import those behaviors or claims.

## Sources of truth and boundaries

- Read `AGENTS.md`, `README.md`, `docs/ARCHITECTURE.md`, and `docs/DEPLOYMENT.md` before changing behavior. Preserve the current React 19/Vite 6 setup unless a dependency change has a clear need.
- `docs/archive/SITE_REDESIGN_IMPLEMENTATION_PLAN.md` and `docs/archive/SITE_REDESIGN_REVIEW.md` describe an earlier redesign that was implemented locally. Use them as history and a baseline for this new visual pass; do not reopen completed product decisions merely because an old plan is written in future tense.
- `frontend/src/App.tsx` owns the upload queue, model selection, real `/api/analyze/compare` requests, result merging/retries, opt-in save before analysis, and CSV export. `frontend/src/api.ts` and `frontend/src/types.ts` define the client contract. Keep server-returned model scores, cutoffs, revisions, recipes, timestamps, image metadata, and errors as the only displayed analysis facts.
- `frontend/src/C2paPanel.tsx` checks the original bytes in the browser on demand; it must remain distinct from model suggestions. `frontend/src/InputInspector.tsx` calls `/api/inspect`; `frontend/src/report.ts` generates real JSON and print-friendly reports.
- `frontend/src/galleryData.ts` imports `docs/GALLERY_MANIFEST.json`; `frontend/src/Gallery.tsx` presents the eight curated cases, their verified origins, credits, actual model runs, disagreements, and misses. Keep the manifest as the content source. Do not use the export's Unsplash gallery or invent source records.
- `frontend/src/History.tsx`, `historyApi.ts`, and `cognitoAuth.ts` own authenticated History, quotas, pagination, reopen, item deletion, and account-wide deletion. Saving is a per-analysis choice made **before** the request; a result cannot be retrospectively saved by toggling a local button. Show actual expiry dates from server data, not a fixed “28 days remaining.”
- Keep guest use, 8 images per batch, JPEG/PNG/WebP, 10 MB per file, independent model selection, partial model failures, and the existing caveats about detector limits. Do not change backend, model thresholds, retention, or cloud architecture for this visual redesign unless a concrete defect requires it.

## Implementation sequence

### 1. Establish a baseline and design map

1. Confirm the worktree state and run the current frontend format/build checks. Record any pre-existing failures.
2. Review the current Analyze, Gallery, and History views in a browser at about 390 px, 768 px, and 1440 px. Include signed-out, empty, processing, success, request error, one-model error, disagreement, and saved states where practical.
3. Extract only the reusable visual patterns from the Figma ZIP. Map them to existing components and list each prototype control as **keep**, **adapt to a real action**, or **omit**. Use the existing backend response and manifest whenever a visual needs data.

### 2. Build the shared visual system and shell

1. Introduce a small set of CSS tokens for colors, type, spacing, borders, and focus states in the existing stylesheets. Carry over the restrained editorial feel without copying the prototype's entire CSS or adding Tailwind merely because the export uses it.
2. Refine the header/navigation and page headings for desktop and mobile. Keep the real Cognito/local-test sign-in controls visible and clearly labeled at narrow widths. Preserve hash navigation and accessible current-page indication.
3. Make shared buttons, notices, status chips, panels, and empty states visually consistent. Avoid decorative controls without an action. Keep loading and error feedback legible.

### 3. Redesign Analyze around the real workflow

1. Arrange the upload area, model choices, privacy/save choice, image queue, and selected result into a clear sequence. Keep `addFiles`, `run`, retries, and `exportCsv` wired to their existing logic. Do not preload fictional queue items.
2. Give the selected image a larger preview and metadata taken from its `File` and API `input`. Render one card per requested model using its returned status, suggestion, score, cutoff, model ID/revision, preprocessing, and timing. Display each model's failure independently and preserve retry behavior. Never combine scores or infer an origin verdict.
3. Keep the on-demand input inspector, on-demand Content Credentials check, JSON report, print/PDF flow, and CSV export discoverable without overwhelming the primary result. Display credential statuses only after the actual check completes.
4. Keep “save to History” as an explicit signed-in choice before analysis. Reflect actual saved/not-saved responses and expiry. Preserve the existing no-save behavior for guest and unsaved requests.

### 4. Redesign Gallery and History with real content

1. Rework Gallery into a visually stronger guess-then-reveal flow using the existing eight manifest cases. Keep source links/credits, model disagreements, and mistakes visible; retain useful filtering or provide an equally clear route to those cases. Do not represent the gallery as an accuracy benchmark.
2. Give signed-out History a clear explanation and real sign-in action. For signed-in users, use the actual list/detail API state, quota and expiry values, loading/errors, pagination, original retrieval, report actions, item deletion, and account-wide deletion. Keep destructive controls explicit and the real confirmation behavior intact.

### 5. Responsive and accessibility pass

1. Inspect phone, tablet, and desktop layouts with long filenames, 8-item queues, tall and wide images, mixed model outcomes, and an empty History. Prevent clipped controls and unwanted horizontal page scrolling.
2. Navigate every key flow with a keyboard. Ensure visible focus, semantic buttons/labels, readable status text, and usable touch targets. Avoid nested buttons and icon-only controls without accessible names.
3. Preserve the current honest wording: scores are model suggestions; Content Credentials are separate signed claims; missing credentials do not establish origin; private History is opt-in.

## Verification and deliverables

- Run `npm run format:check` and `npm run build` from `frontend/`. Run relevant backend checks only if backend code changes. Validate the gallery manifest with the repository's documented command if its data or import changes.
- Exercise real local browser flows against the existing API using non-sensitive known fixtures: guest analysis, each model alone, both models, partial error/retry, invalid and oversized upload, C2PA check, input inspector, CSV/JSON/print export, and empty/reset states. Where authenticated local test accounts are available, check opt-in save, History reopen/delete, quota/expiry messaging, and sign-out. Do not claim hosted account isolation from a local test.
- Capture review screenshots at phone, tablet, and desktop widths for Analyze, Gallery, and History, plus at least one error or disagreement state. Compare the redesign against the Figma visual reference and the original app's behavior.
- Hand back a concise change summary, screenshots, checks run/results, any remaining limitations, and the exact local commit/diff. Keep the redesign local and reviewable; `docs/DEPLOYMENT.md` describes the separate owner-run public update and post-deploy checks.

## Completion criteria

The app looks and works coherently across the three views; every visible control has a real action or is clearly disabled; model and gallery facts come from the existing authoritative data; guest and saved-data behavior is preserved; exports, C2PA, inspector, and History still work; responsive and keyboard checks pass; the frontend format/build checks pass. Do not mark the work complete based on a static mockup alone.
