# Release checks: short implementation plan

> **Local release record.** These checks preceded the public AWS deployment.
> They do not establish hosted account isolation, cost controls, or TLS renewal.
> See [Deployment and operations](DEPLOYMENT.md#remaining-release-and-operations-checks).

**Status:** local browser checklist marked complete, 26 October 2026. The [readiness record](AWS_READINESS_2026-10-26.md) distinguishes recorded tests from checks confirmed by the owner. This plan does not authorize or create AWS resources.

## Simple checklist

- [x] Upload images and get results from both models, including an eight-image batch.
- [x] Check the main screens on desktop and phone.
- [x] Confirm one account cannot see another account's saved image.
- [x] Save or print a report as a PDF and open the resulting file (owner verified).
- [x] Use the site with only a keyboard (owner verified).
- [x] Inspect full History at phone and desktop sizes; verify deleted and expired originals are inaccessible and an expired item offers a browser refresh action.
- [x] Verify the browser's successful deletion feedback with disposable local-test data. The message survived the automatic list refresh, History became empty, and quota returned to 0 of 10.
- [x] Check the C2PA edge behavior (owner confirmed). The recorded local run used a trusted original and a test-only real-suggestion stub for the conflict UI; no real pinned-model conflict fixture was captured in that run. The accepted JPEG, PNG, and WebP upload formats have no unsupported-format input route.
- [x] Decide whether the gallery's images and wording are ready to show publicly (owner marked ready).

## How to finish

1. **Report:** Analyze one image, save/print its report, then open the PDF. Pass when the image, model names and results, C2PA wording, and page layout are readable and match the screen.
2. **Keyboard:** Starting from the page header, use Tab, Shift+Tab, Enter, and Space through upload, Analyze, results, report, gallery, sign-in, and History. Pass when focus is visible and every essential action works without a mouse.
3. **History states:** The full-quota and expired-item browser states, deleted/expired API access checks, and successful browser deletion feedback passed on 26 October. The deletion check used disposable local-test data; its screenshot is linked from the readiness record.
4. **C2PA:** The owner reports verifying the edge behavior. The independently recorded local check used a signed original with a synthetic real model suggestion and showed the signals separately. A reproducible real pinned-model conflict fixture was not retained in that record; this is an evidence limit, not an open checkbox. The accepted upload formats did not yield an unsupported-format case.
5. **Gallery decision:** The owner marked this review complete and ready for public inclusion. Keep the source/rights notes and reveal wording with the released gallery.
6. **Fix and record:** Repair any observed release blocker. Run backend tests and Ruff, then frontend format check and build. Record the date, commit, browser sizes, pass/fail result, and any remaining issue in the readiness record.

**Release gate:** Do not publish if another user can access private History, deleted/expired originals remain readable, results are assigned to the wrong model, or analysis repeatedly fails. Once the checklist passes and the gallery decision is recorded, continue with the measured AWS sizing and cost review in the [AWS implementation plan](AWS_IMPLEMENTATION_PLAN.md).

This checklist covers local browser behavior. Public cloud release also needs
hosted authentication and private storage, request controls, a cost/teardown
review, model-weight usage review, and the C2PA trust-list refresh noted in
[the C2PA record](C2PA_FEASIBILITY.md).
