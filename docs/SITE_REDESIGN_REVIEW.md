# Site redesign review

This records the screen hierarchy and visual baseline for the local redesign.
The supplied baseline artifact is `output/review/input-inspector-desktop.png`;
it shows the earlier dense result cards and inspector on desktop. No older
phone, tablet, batch, or gallery-reveal screenshots were present in the review
folder, so those states are not represented as measured baseline evidence.
Optional History was added after this Analyze/Gallery redesign. Its phone and
desktop checks are recorded in [the local history verification](HISTORY_LOCAL_VERIFICATION_2026-10-25.md),
with screenshots under `../output/review/`.

## Baseline findings

- Upload, result cards, model scores, credentials, inspector, and gallery shared
  one long page, making the next action hard to scan.
- Every uploaded image repeated its full result and action set, multiplying the
  page length for a batch.
- Technical values and source metadata appeared alongside the primary result,
  using small text and several nested bordered panels.

## New screen hierarchy

Analyze, desktop:

```text
Image Origin Studio                                  Analyze   Gallery

Inspect an image with two models.
Compare separate model suggestions and Content Credentials.

┌ Add images · types and limits ─────────────┐  Models for next analysis
│ Choose images                              │  □ V3 E2  □ Community Forensics
└───────────────────────────────────────────┘

Images (n/8)                 Selected image
┌ thumbnail / filename ┐    [preview] filename and file details
│ short outcome         │    model suggestion row     Technical details ▸
└───────────────────────┘    model suggestion row     Technical details ▸
Analyze batch · Export CSV   Content Credentials      Check credentials
                             More actions ▸
```

Analyze, phone:

```text
Image Origin Studio                           Analyze  Gallery
Inspect an image with two models.
┌ Add images · Choose images ┐
Models for next analysis
□ V3 E2
□ Community Forensics

Images (n/8) · Analyze batch
thumbnail filename · short outcome

Selected image · preview and filename
model suggestion · score · cutoff
Technical details ▸
Content Credentials · Check credentials
More actions ▸
```

Gallery uses a compact filtered thumbnail grid. Selecting a case opens one
focused case view; the private guess precedes the reveal. The reveal presents
documented origin, each model suggestion, disagreements and mistakes. Source,
rights, attribution, edits, hashes, and model revisions are behind labeled
details. The case manifest is unchanged.

## Visual review states

During the redesign, the local browser was inspected at 390 × 844, 768 × 1024,
and 1440 × 1000. The empty analyzer, two-file ready queue, gallery grid, and a
single revealed gallery case were viewed. Review screenshots under
`output/review/redesign/` show the empty Analyze view and Gallery grid at
desktop and phone widths, the two-file selected-image view at both widths,
an absent-credential state on a phone, and one revealed gallery case on a
phone. The tablet review was viewed in the browser but was not saved as a file.
