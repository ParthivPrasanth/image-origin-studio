# Next implementation plan — Image Origin Studio

**Current status (25 October 2026):** This began as a proposal and now records
the local implementation and remaining gates. Historical milestone instructions
below describe how features were built; the table is the current status.

| Work | Current state | Evidence or remaining gate |
| --- | --- | --- |
| Input inspector and case report (1–2) | Implemented locally | Backend checks and browser report review; the print-to-PDF browser path still needs a manual saved-PDF check. |
| Challenge gallery (3) | Eight-case local review draft | [Manifest](GALLERY_MANIFEST.json) and source records exist; exact cases, labels, and reveal wording await owner approval before publication. |
| Content Credentials (4) | Local browser prototype | [C2PA checks](C2PA_FEASIBILITY.md) include trusted, valid, invalid, and absent cases. Unsupported format and a credential/model-real conflict still lack a recorded browser check. |
| Robustness lab (5) | Skipped by owner | No implementation planned. |
| Site redesign | Implemented locally | [Review screenshots](SITE_REDESIGN_REVIEW.md) exist; complete the [remaining live-state matrix](SITE_REDESIGN_IMPLEMENTATION_PLAN.md) before release. |
| Optional private history | Implemented for localhost test identities | [Verification record](HISTORY_LOCAL_VERIFICATION_2026-10-25.md) covers SQLite, exact originals, ownership, quota, deletion, and expiry. Hosted sign-in and cloud storage remain future work. |
| AWS readiness and deployment (6–7) | Not started | Resource measurements, container verification, costed architecture, spending gate, and cloud checks remain. |

The sample report artifacts under `output/` are review examples, not accuracy
evidence. The owner reports checking the earlier C2PA, saved-report, and gallery
flows. That review does not close the specific post-redesign browser matrix.

## Goal and scope

Turn the current local two-model comparison into a useful **image inspection
workbench**, then prepare an AWS release that the owner can understand and
operate. The next work is product experience and engineering. **Do not run a
new model benchmark, retrain or retune V3 E2, or make a new accuracy claim.**
Keep both existing model revisions, preprocessing recipes, and thresholds
fixed. Continue to describe their outputs as model suggestions.

The planned sequence is:

1. Show the exact input views and processing steps for each selected model.
2. Let users export a readable, reproducible case report.
3. Build a small, source-documented challenge gallery.
4. Add a separate C2PA Content Credentials panel.
5. Skip the optional robustness lab, as the owner decided.
6. Add opt-in local history and verify deletion and ownership (complete for local test identities).
7. Measure runtime resources and prepare a costed AWS design.
8. Deploy only after the design and spending gate are reviewed.

The original first product increment ended after steps 1 and 2. The owner then
requested step 3 as the next increment. Each later step has its own review
gate, so the application remains usable if cloud work is deferred.

## Historical starting point before the local milestones

The bullets in this section record the initial state when this plan was written;
they are not a description of the current API or interface.

- `frontend/src/App.tsx` handles uploads, model selection, separate results,
  retries, and CSV export. The local batch cap is eight images.
- `backend/app/main.py` offers `POST /api/analyze/compare`; it returns model
  scores, revisions, thresholds, elapsed time, and per-model errors. It does
  not return an image hash, dimensions, or inspectable input views.
- `backend/app/v3_e2.py` first makes a 224-pixel square view. Its FFT features
  use that view; its MobileNet branch applies the pinned TorchVision transform
  afterward. `backend/app/model.py` uses a separate resize and center crop for
  Community Forensics. The inspector must respect those distinct paths.
- Uploaded image bytes and results currently live only in browser/server
  process memory. The API is bound to localhost; AWS is not deployed.

## Milestone 1 — Input-view inspector

**User experience.** A result card gains a clear “Inspect model inputs”
action. An expanded panel shows the original image and separate labeled
previews for V3 E2's FFT input, V3 E2's MobileNet input, and Community
Forensics' input when those models were selected. Show pixel dimensions and
the crop/resize recipe beside each preview. Explain that display previews
show pixels before tensor normalization and **do not explain why a model made
its decision**. Keep disagreement and errors visible next to the inspector.

**Implementation path.** Extract reusable preprocessing/view functions in
`backend/app/v3_e2.py` and `backend/app/model.py`, while preserving exact
current inference behavior. Add an on-demand, stateless inspection API in
`backend/app/main.py` that validates the uploaded file through the existing
limits and returns small displayable views plus the original file's SHA-256,
dimensions, format, and recipe identifiers. The browser re-sends the file
only when the user opens the inspector. Split the growing React screen into
focused components and API/types modules under `frontend/src/`; avoid adding
a new UI framework.

**Done when:**

- The preview generation and real inference use the same preprocessing
  functions; a parity check catches accidental changes to model inputs.
- Each selected model's view is correctly labeled; V3 E2's two branches are
  distinguishable. Unselected or failed models do not imply a successful
  inspection.
- Valid JPEG, PNG, and WebP inputs work; corrupt and oversized inputs fail
  clearly. Closing/removing an image releases preview object URLs.
- The panel works on phone and desktop widths, with keyboard operation and
  readable focus, loading, and error states.

**Stop condition:** if a display preview cannot accurately represent a
model's tensor input, label the difference precisely and do not call it the
“exact pixels seen.”

## Milestone 2 — Downloadable case report

**User experience.** Each completed image has “Download case report.” The
report records the original byte hash, filename, format and dimensions,
analysis timestamp, requested models, each success or error, model IDs and
revisions, separate scores and thresholds, preprocessing recipe versions,
and the limitation statement. It identifies disagreements without creating
a combined verdict. A batch CSV remains available.

**Implementation path.** Add a versioned report data shape in
`frontend/src/` and generate it from the exact result snapshot plus the
server-confirmed input metadata. Offer machine-readable JSON and a
print-friendly, one-image report that the user can save as PDF. Keep report
generation in the browser so the server does not retain uploads or reports.
Do not embed the original image in the portable report by default; if an
image-inclusive option is added, make it explicit to the user. Record
partial-model failures rather than dropping them.

**Done when:** a downloaded report can be matched to the analyzed original
bytes and reproduced from its model/recipe versions; it remains accurate
after model selection changes, retries, and partial failures. Test file names
and user-controlled text for safe rendering. Verify the printed report at
phone and desktop layouts and inspect the resulting PDF manually.

**Review gate after milestone 2:** owner reviews the actual inspector screen,
one JSON report, one saved PDF, and the updated Windows README. Decide
whether the interface is clear enough before adding the lab.

## Milestone 3 — Source-documented challenge gallery

**User experience.** A visitor can inspect a curated image, make a private
guess about its origin, then reveal the documented source and both model
suggestions. The gallery can filter by documented origin, model
disagreement, and model mistake. Incorrect predictions remain visible. A
short explanation states how each origin was documented and where certainty
ends; a publisher's “real” label alone is not independent proof of camera
capture. Gallery labels never change based on model output.

**Implementation path.** Start with a small, varied set (roughly 8–12 cases),
not a large dataset. For every image, record a source page, creator or
generator, permitted display/redistribution terms, origin evidence,
attribution, exact file hash, and any edits. Obtain appropriately licensed
copies before publishing them; the existing 12-image public pilot must not
be copied into the gallery automatically because its photo origins were not
individually verified and its generated-image redistribution terms need
review. Store only optimized display copies allowed by the license, with a
manifest in `docs/` and gallery assets under `frontend/` or a controlled
asset host. Pin the model revisions used for the displayed suggestions.

This requires running the current models on selected gallery examples to
show their suggestions. It is a **curated product demonstration**, not a new
benchmark: do not report gallery accuracy, tune the models from it, or
describe selected cases as representative performance. The visitor's guess
stays in browser memory; no account or score tracking is required.

**Done when:** every public image has a checked origin/rights record and a
working source link; revealed answers, filters, keyboard interaction, and
mobile layout work; the examples include honest model mistakes or
disagreements. If origin or display rights cannot be established for a
candidate, exclude it rather than weaken the label.

**Review gate:** owner approves the exact gallery cases, their labels, and
the reveal wording before they are published. Current candidate records are
`docs/GALLERY_MANIFEST.json`, `docs/GALLERY_PUBLIC_AI_SOURCES.md`, and
`docs/GALLERY_CAMERA_SOURCES.md`; optimized candidate assets are under
`frontend/public/gallery/candidates/`. The app labels these
as a local review draft. Do not deploy the current frontend bundle publicly
until the owner accepts this set.

## Milestone 4 — C2PA provenance panel

**User experience.** On the original uploaded file, show whether a Content
Credential is present, whether its signature/content binding validates,
the signer or issuer when available, and declared creation/edit actions.
Keep this panel visually and verbally separate from the V3 E2 and Community
Forensics scores. “No credential found” means **unknown**; a valid
credential verifies signed claims, not the truth of the depicted scene.
Ordinary EXIF fields, if later displayed, must be marked as unverified
metadata rather than cryptographic provenance.

**Implementation path.** First make a small feasibility prototype with a
pinned version of the official `@contentauth/c2pa-web` SDK on sample files
with valid, invalid, absent, and unsupported credentials. Confirm supported
formats, WebAssembly loading, trust-list behavior, browser performance, and
whether validation can happen locally without transmitting private uploads
to another service. Lazy-load the validator only when the panel opens. Read
the original bytes **before** any crop, JPEG conversion, or resizing, which
could remove or invalidate credentials. Map SDK states to distinct UI text:
valid and trusted, valid but signer trust unresolved, invalid, absent,
unsupported, and validation error. Record the credential result in the case
report as a separate section with validation method and SDK version.

**Done when:** real sample credentials exercise each state; an altered file
does not display as valid; an image without credentials is not labeled real
or fake; errors do not affect either model's result; the report preserves
the same distinction. Cite the [C2PA explainer](https://spec.c2pa.org/specifications/specifications/2.4/explainer/Explainer.html)
in user-facing help text.

**Stop condition:** if signature, content-binding, or trust status cannot be
verified reliably in this app, show “unable to validate” and defer the panel
instead of presenting parsed metadata as verified provenance.

## Milestone 5 — Optional robustness lab (skipped by owner)

**User experience.** For one image at a time, a separate “Try image changes”
panel compares the original with a *small fixed set* of declared variants:
start with JPEG quality 90, 75, and 50; consider a single resize variant
only after timing the first version. Display the transformed image, exact
settings and byte hash, then each selected model's score change and decision.
The original result remains visible. No A–F grade, “resilience score,” or
claim about a named social network's pipeline.

**Implementation path.** Make transformations deterministic in the backend,
with explicit encoding settings. Reuse the same validation and inference
paths, cap variant count and input size, and run locally in sequence. Add
visible progress and cancellation/close behavior in the UI. This is an
exploratory tool for the user's chosen image, **not** a new dataset-wide
evaluation or a threshold-tuning loop.

**Done when:** the report can record the original and transformed hashes,
settings, separate scores, errors, and timing; tests verify transformations
are reproducible and do not silently alter the original result. Measure
latency and memory before enabling the lab for public use.

**Stop condition:** if repeated inference makes the local app unstable or
unreasonably slow, keep this feature disabled while the rest of the workbench
ships.

## Milestone 6 — AWS readiness package

This milestone prepares a decision; it does not create cloud resources.

1. Measure cold model download/load time, peak RAM, and warm latency for V3
   E2, Community Forensics, and both loaded together. Include one image,
   a small batch. These are **resource
   measurements**, not model-accuracy evaluation.
2. Build and test a backend container locally, including pinned-weight
   checks, startup behavior, health/readiness, and a restart. Record its
   image size and expected memory/CPU requirement.
3. Choose the simplest AWS architecture that fits the measurements. Draft
   a diagram explaining the browser, API, private image storage, model
   worker, job status, and logs in beginner-friendly terms. A queue is
   justified only if synchronous requests cannot meet measured needs.
4. Specify file ownership, maximum size and request rate, retention and
   deletion, authentication needs, error/retry behavior, and observability.
   Private uploads must never become public bucket objects.
5. Create a region-specific price estimate using **current AWS prices**,
   expected usage assumptions, a budget alert, and exact setup and teardown
   instructions. Keep account IDs, credentials, and private images out of Git.

**Review gate before spending:** owner reviews the services, estimated
monthly cost and assumptions, budget alert, privacy behavior, and teardown.
No paid AWS resource is created before that review. If the host is too
expensive, revise the architecture or defer deployment.

## Milestone 7 — Deployment and evidence

After the AWS gate, implement the chosen infrastructure and deployment path.
Verify a real browser upload through processing and result retrieval; cover
an invalid file, model error, retry, duplicate job delivery if a queue is
used, and deletion. Capture observed latency, memory, errors, and actual
charges against the estimate. Add a step-by-step Windows operator guide:
how to deploy, inspect logs, recover a failed job, set a budget alert, and
remove all resources. Mark the app “deployed” only after these checks pass.

## Decisions for the owner's review

| Decision | Proposed default | Reason |
| --- | --- | --- |
| First build slice | Inspector + case report, implemented locally | Immediately useful with the current two-model app. |
| Report formats | JSON plus print/save-as-PDF page, implemented locally | Reproducible data and a readable artifact without server report-file storage. |
| Original image in report | Excluded by default | Limits accidental sharing of private image content. |
| Gallery | Eight-case local review draft | Makes the app engaging without claiming benchmark accuracy; publication review remains. |
| C2PA | Local prototype implemented | Adds separate provenance information; remaining browser cases are listed above. |
| Robustness lab | Skipped by owner | Keep the current workbench focused. |
| Accounts/history | Local test identities and opt-in SQLite history implemented | Exact originals have 30-day retention and 10-item/50-MB per-identity limits; hosted identity and storage remain. |
| Cloud services | Decide after resource measurements and price review | Avoids paying for an oversized architecture. |

## Work excluded from this plan

No new model benchmark, model retraining, threshold tuning, accuracy claim,
heatmap presented as causal explanation, composite authenticity score,
perceptual-hash result cache, or automatic collection of users' images.
Gallery examples are not an accuracy sample. The existing evaluation records
remain available with their stated limits.

## Planned verification and handoff

For each milestone, run the relevant backend tests and Ruff, frontend format
check and build, then manually check real local inference and browser states.
Review the interface at phone, tablet, and desktop widths with keyboard,
empty, loading, partial-error, and disagreement states. Keep README,
`docs/WIREFRAMES.md`, and `docs/DEPLOYMENT.md` aligned with what actually
ships. At each handoff, report what was built, what was measured, what is
planned, and the next gate.
