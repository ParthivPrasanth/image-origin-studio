# Site redesign implementation plan

**Status:** implemented locally, pending owner screen review and the remaining
live-state checks, 25 October 2026. The owner verified the earlier C2PA flow,
report, and gallery and chose to skip the optional robustness lab.

**Implementation checkpoint (25 October 2026):** The owner subsequently
authorized this redesign. The Analyze/Gallery navigation, selected-image
workspace, simplified result and credential presentation, and focused gallery
are implemented locally. Frontend formatting and production build pass;
13 targeted backend tests pass. Empty, two-file ready, gallery grid, and
one-case reveal states were checked in a browser at phone, tablet, and desktop
widths. Review screenshots are in `../output/review/redesign/`; see
`SITE_REDESIGN_REVIEW.md`. The owner still needs to review those screens.
The complete live analyzed, partial-error, credential-conflict, inspector,
and PDF-print visual matrix has not yet been rechecked after the redesign.

## Goal

Make Image Origin Studio feel like a focused image-inspection tool. A visitor
should quickly understand how to add an image, see each model's suggestion,
check Content Credentials, and inspect details when needed. Keep the current
models, thresholds, preprocessing, provenance validation, report content, and
gallery source records intact.

## What is making the current page feel crowded

The current `frontend/src/App.tsx` puts the upload workspace, detailed results,
an explanatory aside, and the entire challenge gallery on one page. Each
uploaded image expands into two model cards, a Content Credentials panel, an
input inspector, multiple export links, and another analysis action. With a
batch, those full cards repeat up to eight times. The gallery's two-column
cards also expand into long model and source sections after reveal.

The styling in `frontend/src/style.css` and `frontend/src/gallery.css` adds
many nested borders, tinted boxes, rounded corners, tiny 10–12 px metadata,
eyebrow labels, step badges, and decorative symbols. An existing desktop
review screenshot (`output/review/input-inspector-desktop.png`) confirms the
dense model cards and inspector text. A fresh full-page visual audit is still
needed when implementation starts.

## Proposed design direction

Use a quiet, editorial research-tool style: one clear sans-serif type family,
larger readable body text, generous whitespace between major sections, a
neutral canvas, dark text, and one restrained accent color for actions and
links. Use borders only where they separate meaningful regions. Remove the
decorative brand glyph, numbered step badges, oversized empty-state icon,
pill labels, unnecessary shadows, and repeated tinted cards. Keep the name
**Image Origin Studio** and avoid new marketing claims or a generic analytics
dashboard look.

The top navigation has two clear destinations: **Analyze** and **Gallery**.
The gallery becomes its own view rather than appearing below the analyzer.
Use a lightweight URL-backed view switch so Back, refresh, and a direct gallery
link work; a new routing framework is unnecessary for two views. Put a short
plain-language explanation of model limits near results and move the full
method explanation into an accessible “How to read this” disclosure.

## Implementation steps

### 1. Establish a visual baseline and the new screen hierarchy

- Capture the current empty, one-image, two-model, batch, credential-conflict,
  error, inspector-open, and gallery-revealed states at desktop, tablet, and
  phone widths. Record the three most visible problems in each state.
- Draw simple desktop and phone wireframes before changing components. The
  primary path is **Add image → Analyze → Read the selected image's results**.
- Set a small type, spacing, color, and surface system in CSS. Target body
  text around 14–16 px and metadata no smaller than 12 px. Make primary and
  secondary actions visually distinct without decorative controls.

**Files:** `frontend/src/style.css`, `frontend/src/gallery.css`, and a small
wireframe or review image under `docs/` if useful.

### 2. Separate Analyze and Gallery

- Keep the header compact with the product name and two navigation links.
- Show a focused Analyze view on first load. The Gallery view keeps its
  source-documented cases, filtering, guessing, and reveal behavior.
- Make navigation keyboard operable, preserve the selected view in the URL,
  and restore the correct view after refresh or Back.

**Files:** `frontend/src/App.tsx`, `frontend/src/Gallery.tsx`, shared CSS.

### 3. Rebuild the analysis workspace around one selected result

- Replace the large side-by-side upload and empty-results cards with a compact
  upload area and plain model choices. Keep both models selected by default;
  show the file-size and format limits in one line.
- After upload, show a compact list of selected images with thumbnail,
  filename, processing state, and short model outcome. Selecting an image
  opens one full detail view. This prevents eight large result cards from
  filling the page at once.
- Give the selected image a clear hierarchy: image and filename first, then
  the two model suggestions, then the independent Content Credentials status.
  Keep batch Analyze and CSV export near the list rather than repeating them
  inside each detail view.
- Preserve retry, remove, and reanalyze behavior. Do not let switching the
  selected image mix results or credentials between files.

**Files:** primarily `frontend/src/App.tsx` and `frontend/src/style.css`.
Extract a `ResultDetail` or `ResultList` component only if it makes the state
flow easier to read; do not add a UI framework.

### 4. Simplify result detail without hiding important distinctions

- Display each model as one readable comparison row: model name, suggestion,
  AI model score, and its cutoff. The two complementary score bars and long
  model IDs move into a “Technical details” disclosure; the JSON report still
  carries all values. Keep errors and model disagreement prominent.
- Show Content Credentials as a separate row with its own **Check
  credentials** action. When checked, show validation state and the signed
  claim; put signer, actions, and validation codes in expandable details.
  Never merge this with a model score or hide a credential/model conflict.
- Group **Inspect model inputs**, **Download JSON**, **Print or save PDF**, and
  **Analyze again** under a tidy secondary-actions area. The inspector opens
  in the selected image's detail view, with readable image previews and
  captions.
- Keep the existing report schema and C2PA validation behavior. This step
  changes presentation and navigation only.

**Files:** `frontend/src/App.tsx`, `frontend/src/C2paPanel.tsx`,
`frontend/src/InputInspector.tsx`, and CSS. Touch `frontend/src/report.ts`
only if a presentation change requires it; report data must remain stable.

### 5. Make the gallery faster to scan

- Start with a compact image grid and a short introduction. Each card shows
  the image and title; guessing and revealing happen in a focused case view
  or expanded card, one case at a time.
- On reveal, show documented origin and both model suggestions first. Keep
  mistakes visible. Put source evidence, attribution, rights, edits, hashes,
  and model revisions in clearly labeled details rather than long default
  paragraphs.
- Keep the owner-approved case assets, labels, sources, and reveal wording.
  The redesign must not alter the documented origins or suppress a model miss.

**Files:** `frontend/src/Gallery.tsx`, `frontend/src/gallery.css`.

### 6. Verify the new experience before AWS work

- Walk through empty, loading, success, partial error, batch-eight, model
  disagreement, credential absent/valid/invalid, credential/model conflict,
  inspector, report, and gallery reveal states.
- Check keyboard focus, screen-reader labels, browser Back/refresh, long file
  names, touch targets, and layouts at roughly 390, 768, and 1440 px. Inspect
  actual screenshots at each width and fix overflow or tiny text.
- Run frontend formatting and build plus the existing relevant backend tests.
  Confirm that model requests, result values, C2PA checks, JSON export, and
  PDF print still work. Keep original images out of Git.

## Done when

At desktop and phone widths, the first screen has one obvious upload action;
a user can find both model suggestions and the separate credential state for
one selected image without scanning eight full cards. The gallery is reachable
from the header and directly by URL. The detailed model, provenance, source,
and report information remains accessible. The owner has reviewed real
screenshots of the empty, analyzed, and gallery states. Then proceed to the
AWS resource measurements and cost design in the main implementation plan.
