# Agent guide for Image Origin Studio

This file records the working agreement for this repository. Follow the user's current request first. Keep this guide aligned with the code and documentation as the project changes.

## Project and scope

- This is an independent Git repository for an AI image screening web app. Do not copy code, branding, results, or model claims from the earlier CCD project or a collaborator's detector.
- The supplied CCD synopsis is background for cloud architecture. Its DINOv2/FFT detector is **not** the model in this app, and its proposed AWS services are **not** deployed here.
- The original pasted project plan calls for a useful local detector, batch uploads, a known-origin gallery, optional accounts and private history, honest evaluation, deliberate interface design, and a staged cloud release. **AWS is the owner's chosen deployment target.**
- The owner is new to cloud deployment. Explain unfamiliar services and decisions in plain language, maintain runnable Windows instructions, and document costs, verification, and teardown before AWS work.
- Keep the owner informed as work progresses, including decisions, completed changes, failed checks, and the next step.
- Keep documentation organized and understandable so the owner can learn how the project works and future work can build on it.

## Current snapshot (29 October 2026)

- The local app uses React/TypeScript in `frontend/` and FastAPI in `backend/`. It offers the owner's locked V3 E2 model and the pinned Community Forensics external baseline, individually or side by side. Keep their preprocessing and thresholds separate. See `backend/app/v3_e2.py` and `backend/app/model.py` for authoritative inference details.
- V3 E2 comes from the separate, read-only ML Project. Package inference-only artifacts with hashes; never depend on that sibling folder at runtime or alter its training, lock, or final-test evidence. The pretrained MobileNetV3 backbone is frozen; the owner trained the fusion head. See `docs/DUAL_MODEL_EVALUATION.md` for claim boundaries.
- The first app model, `jacoballessio/ai-image-detect-distilled`, made clear errors on the owner's test folder. `Thermostatic/community-forensics-frontier-detector-2026-08` replaced it and now serves as the external baseline. Its selection protocol and results are recorded in `docs/MODEL_REVIEW.md` and `docs/EVALUATION.md`.
- Single and batch uploads, previews, per-model results and errors, retry, CSV export, the on-demand input-view inspector, and per-image JSON/print-friendly case reports are implemented. A separate on-demand C2PA browser check reads original file bytes and keeps credential claims distinct from model suggestions; see `docs/C2PA_FEASIBILITY.md`. The source-documented eight-case gallery is published. Guest and unsaved analyses are not added to History. Optional private history works for localhost test identities behind `IOS_LOCAL_TEST_AUTH=1`; see `docs/HISTORY_LOCAL_VERIFICATION_2026-10-25.md`. The owner has also deployed Cognito sign-in and S3/DynamoDB History and confirmed one hosted save. Background workers are not part of the deployed architecture.
- On 29 October 2026 the owner deployed a public HTTPS site at `https://35.154.237.144/` on one Ubuntu EC2 host in Mumbai. Nginx serves the React build and proxies to a Dockerized FastAPI service on loopback. The owner confirmed both models, sign-in, and History saving; the public root and health endpoint returned 200. The deployment record does not confirm second-account isolation, a budget alert, or inspection of the installed certificate-renewal schedule. `docs/DEPLOYMENT.md` is the maintained current status; the 26 October readiness/proposal documents are dated predeployment evidence. The owner later chose a USD 20 planning ceiling, superseding the proposal's USD 35 figure. Do not represent local measurements as EC2 capacity or claim unverified hosted controls passed.
- `README.md` is the public entry point, `docs/README.md` indexes current and dated material, `docs/ARCHITECTURE.md` explains the code/data flow, and `docs/DEPLOYMENT.md` tracks the live setup and outstanding checks. Check code and current host evidence before repeating this snapshot in a user-facing claim.
- `docs/PRODUCT_OPPORTUNITIES.md` is a researched proposal, not an implemented feature list. Review the first vertical slice with the owner before changing product direction.

## How to work with the owner

- Make concrete, reviewable progress on authorized work. For a major change in model, product direction, data retention, or hosting, explain the evidence and tradeoffs and involve the owner in the decision. Routine implementation and reversible fixes can proceed directly.
- Favor practical, presentation-aware choices and fast iteration. Use reasonable workarounds and curate clear examples that show the product well; do not turn every small product decision into a research protocol or delay implementation for nonessential perfection.
- Keep the repository organized: put API code and tests in `backend/`, UI code in `frontend/`, repeatable scripts in `scripts/`, and durable explanations or evidence in `docs/`. Prefer focused changes over new frameworks or services without a demonstrated need.
- Use restrained, purposeful UI design. Review real screens at phone, tablet, and desktop widths, plus keyboard, loading, empty, error, and incorrect-prediction states.
- When reporting progress, separate what is implemented, what was measured, and what is planned. State failures and unfinished gates plainly.

## Model and evaluation rules

- Call outputs **model scores** or **model suggestions**. They are not proof of origin or calibrated probabilities for arbitrary uploads. Show each model's version, preprocessing, and fixed decision rule; never average their scores or silently designate one as the truth.
- Keep preprocessing and label mapping tied to each exact pinned model. If a model changes, update the code, artifacts and lockfiles if needed, UI wording, README, evaluation record, and reproducibility checks together.
- The owner's `images test` folder has partly uncertain origins and a duplicate. It is useful for diagnosing visible failures, not for fitting thresholds or making accuracy claims. Do not commit those images or a file-level report containing their private paths.
- The recorded 60-image So-Fake-OOD comparison helped select the current model. It is no longer an untouched final test set. Do not retune or reselect against it, or describe its 85% balanced accuracy as expected performance on new uploads.
- V3 E2's 92% result belongs to a different, viewed COCOXGEN/COCO final set. Do not compare that percentage directly with Community Forensics' 85%, or retune from V3's final and post-hoc diagnostic groups. A head-to-head accuracy claim needs the same new known-origin images and a protocol fixed before scoring.
- The public 12-image paired pilot in `docs/PUBLIC_PILOT_2026-10-24.md` is a diagnostic with one AI generator, one real-photo source, and unknown baseline training overlap. Keep its errors visible; do not use it to retune either threshold or claim general superiority.
- For new accuracy claims, first agree on a fixed protocol using independently sourced images with verified origin, source/license, generator or camera, transformations, and hashes. Check for duplicates and possible training or selection overlap. Report class counts, confusion matrix, subgroup failures, and concrete mistakes; keep gallery misses visible.

## Privacy, cloud, and release gates

- Keep local images, manifests, diagnostic outputs, model downloads, virtual environments, and secrets out of Git. The ignored `.local/`, `model-cache/`, and `.venv/` directories are for local work; inspect changes before committing.
- Local opted-in storage has ownership, private access, deletion, and retention checks; review them again for the production identity and file store. Before public exposure, address request limits, hosted authentication, and failure handling. The current localhost API is not a production service.
- Measure cold load, peak memory, and inference time for each model and both loaded together before choosing the AWS compute service or changing the provisional batch limit. Explain the architecture in beginner-friendly terms and show how to run, monitor, and stop it.
- Plan the AWS path around private image storage, an API, background processing if measurements justify it, a result store, and logs. S3, SQS, a model worker, DynamoDB, and CloudWatch are candidates from the synopsis, not commitments to deploy every service. Select the exact AWS services, region, and image retention rules from measured requirements.
- Build AWS documentation alongside implementation: account and permission prerequisites, what each service does, reproducible setup or infrastructure code, verification steps, expected charges, monitoring, and exact teardown steps. Keep credentials and account identifiers out of the repository.
- Before creating paid AWS resources, review the exact services, current price estimate, budget alert, and teardown steps with the owner. Do not claim deployment until private uploads, processing, results, failure handling, and deletion have been verified end to end.

## Local verification

Run commands from this repository root in PowerShell. Follow `README.md` for initial installation and startup.

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m ruff check backend
cd frontend
npm run format:check
npm run build
```

API tests use a stub detector. If changing real inference, also run a pinned-model smoke check through the actual API and record the model revision and result. Verify UI behavior in a browser when changing user flows. Run only the checks relevant to the change, and report anything unverified.
