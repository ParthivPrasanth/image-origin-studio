# Screen plan

These wireframes began before the first interface implementation. The local app now has separate Analyze, Gallery, and History views. Analyze supports one image or a small batch, with V3 E2, Community Forensics, or both selected before analysis. The local History flow was checked at phone and desktop widths; see [the verification record](HISTORY_LOCAL_VERIFICATION_2026-10-25.md). The first two sketches below are historical; the [redesign review](SITE_REDESIGN_REVIEW.md) shows the current Analyze and Gallery hierarchy.

## Original upload and empty-result sketch (historical)

```text
Header: Image Origin Studio                         Research model demo

Explore what the model sees.
Plain-language limitation statement

01 Choose images                  02 Review results
┌─────────────────────┐           ┌──────────────────────────────┐
│ Drop or choose files│           │ Empty-state explanation      │
│ File types and limit│           │                              │
└─────────────────────┘           └──────────────────────────────┘
Choose models: [V3 E2] [Community Forensics] (both selected by default)
Local privacy note

How to read a result / credited model
```

## Original processing and result sketch (historical)

```text
Choose images                    Review results
                                [Analyze images] [Export CSV]
                                [thumbnail] name   Processing…
                                [thumbnail] name   V3 E2 suggestion and score
                                                   Community Forensics suggestion and score
                                                   Disagreement note if labels differ
                                                   Each model's cutoff, version, and time
                                                   [Inspect model inputs]
                                                   Original display + selected model pixel views
                                                   [Check Content Credentials]
                                                   Separate validation and signed creation claim
                                                   [Download case report JSON]
                                                   [Print / save report as PDF]
```

## Batch and Content Credentials

The Content Credentials panel reads the original selected file on demand. It
shows validation and signer trust separately from model scores. If a validated
credential declares AI generation while a model suggests real, both remain
visible with a conflict note; the case report records the same distinction.

The batch view is the same result list, capped at eight files for the local demonstration. Each row has its own result, error, and retry. The UI must never imply that guest results persist after the browser session.

## Optional private history — implemented local flow

This flow is for local development only. A local test sign-in must be enabled
by starting the API with `IOS_LOCAL_TEST_AUTH=1`; it is off by default and is
not a production account system or Cognito integration. Guests can continue to
Analyze and Gallery without signing in, and guest files and results are never
saved to history.

```text
Analyze (signed in as a local test identity)
┌────────────────────────────────────────────────────────────┐
│ [ ] Save this analysis to my history                       │
│ Off by default. If enabled, keep the exact original file    │
│ and result for 30 days.                                     │
└────────────────────────────────────────────────────────────┘
After analysis: Saved until <date>  |  View History
               Save failed: result is available but not saved

History
┌────────────────────────────────────────────────────────────┐
│ 10 items / 50 MB per identity; 500 MB total originals      │
│ <name> <saved date> <expires> [Open]                       │
│ Open: exact original, result snapshot, report, [Delete]    │
│ Empty / expired / deleting / storage-error states           │
└────────────────────────────────────────────────────────────┘
```

The save control is explicit and begins off. Saving retains unmodified bytes,
which may include EXIF location data. Show expiry and quota, allow deletion,
and stop access immediately when an item expires or is deleted. The app does
not encrypt local files itself. The local sign-in, opt-in save, exact-original
retrieval, quota enforcement, deletion, and expiry checks are recorded in the
linked verification note. Hosted sign-in and storage remain separate work.

## Challenge gallery

The separate Gallery view has eight source-documented cases. A neutral title
and display image appear before reveal; the visitor selects a private camera
photo or AI-generated guess. Reveal shows the documented origin, both pinned
model suggestions, any disagreement or conflict, and the source page,
attribution, rights, edits, and exact display-file hash. Filters show origin,
disagreement, and model conflict. Guesses remain in tab memory and no gallery
accuracy is calculated. On 26 October 2026, the owner marked the exact cases
and wording ready for public inclusion.

## Visual review checklist

- Phone, tablet, and desktop widths
- Keyboard access to file selection, analyze, retry, remove, and CSV export
- Ready, processing, per-model error, partial success, and result states
- One-model and both-model layouts; changing the selector does not relabel existing results
- Disagreement remains visible; a failed model can be retried without discarding the other result
- Inspector loads on demand, omits failed/unselected model views, and has a clear normalization caveat
- Report preview includes original-byte hash, each model's pinned recipe and failure state, and no embedded original image
- Incorrect predictions remain visible as predictions, never rewritten as known origin
- Gallery image fits its card without covering the guess controls; source links,
  filters, keyboard selection, and mistakes remain legible after reveal
