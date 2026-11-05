# Frontend redesign: local implementation and review

**Status: implemented and reviewed locally on 4 November 2026; not deployed to the public AWS host by this record.** This is the outcome of the [redesign handoff](FRONTEND_REDESIGN_HANDOFF_2026-11-04.md). The Figma Make ZIP supplied visual direction only; its simulated analysis, account flow, and substituted gallery items were not imported.

## What changed

- Analyze now has a numbered setup area, a horizontal eight-image queue, a larger selected-image preview, and separate cards for each requested model. The displayed input metadata, suggestions, scores, decision cutoffs, model identifiers, revisions, preprocessing, timing, errors, and save status come from the existing API response.
- Upload limits, independent model selection, partial failures and retries, opt-in saving before analysis, the input inspector, browser-side Content Credentials check, CSV export, and per-image JSON and print reports remain connected to the existing handlers. Clearing a batch revokes its local previews. Retrying one model preserves the earlier saved-History status.
- Gallery keeps the eight source-documented cases, filters, private guess-then-reveal behavior, credits, disagreements, and recorded mistakes. An opened case now has a larger image and a case navigation rail.
- History keeps the real authenticated list, quota, expiry, original retrieval, report, and deletion flows. Its signed-out view offers the configured Cognito sign-in action or disposable local test identities when available.
- The shared styles use a warm paper background, restrained teal, consistent focus outlines, and layouts reviewed at phone, tablet, and desktop sizes.

## Local verification

- Frontend format check and production build passed.
- Backend tests passed (60), backend lint passed, and the gallery manifest verifier confirmed eight records and distinct display assets. These backend tests use stub detectors and do not measure model accuracy.
- Browser review at 390, 768, and 1440 px found no horizontal page overflow or console errors across Analyze, Gallery, and History.
- A public, non-sensitive gallery image was analyzed as a guest with each model alone and both together. An initial local Community Forensics failure came from an unwritable default model-cache path; restarting the API with the documented repository `HF_HOME` setting allowed a successful independent retry.
- Browser checks covered eight queued images, invalid and oversized upload feedback, a corrupt-image API request and retry, a partial model error, an absent Content Credential, the on-demand input inspector, CSV and JSON downloads, and the print report view. A Gallery case with a documented model disagreement was revealed by keyboard.
- A disposable local test identity opted in before analysis, saved a result, reopened the exact original and stored result, observed quota and expiry from the API, deleted the test item, and signed out.

Local review screenshots and the exact frontend patch are retained under `output/redesign-review-2026-11-04/` and excluded from Git. They are review artifacts, not evidence of the public host.

## Remaining release work

The public host still needs a separately reviewed update built from an identified commit, with the previous image and configuration recorded for rollback. Follow [Deployment and operations](../DEPLOYMENT.md) for packaging and post-deployment checks. This local review did not verify hosted Cognito, account isolation, History pagination, account-wide deletion, or a file containing a validated Content Credential. It does not close the deployment guide's outstanding live security, cost, TLS, retention, or capacity checks.
