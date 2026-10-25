# Image Origin Studio

A local web app for comparing two independent AI-image screening models. This is a **new project and Git repository**. It does not import the earlier CCD detector or claim that its DINOv2/FFT architecture is used here.

**V3 E2** is the owner's trained model from the separate ML Project: a learned fusion head on 64 FFT features and 848 features from a frozen, ImageNet-pretrained MobileNetV3-Small backbone. Its training-fitted scalers and head are packaged here; the backbone weights are obtained from TorchVision and hash-checked. E2 retains its locked preprocessing and 0.5 AI decision threshold. Training the fusion head is the owner's work; the pretrained backbone is credited to TorchVision.

**Community Forensics** is the external baseline: [Thermostatic/community-forensics-frontier-detector-2026-08](https://huggingface.co/Thermostatic/community-forensics-frontier-detector-2026-08) (MIT license), pinned to commit `16db135220b318d811b207db576d90368980b595`. Its 44 MB ONNX weights are checked against the published SHA-256 before loading. The app follows its model card's preprocessing and published 65% AI flagging cutoff. Neither model establishes provenance.

The first model failed badly on a small folder of user-supplied images, particularly those provisionally labeled real. A separate 60-image, dataset-labeled check favored this replacement: 25/30 real and 26/30 generated images correct, versus 18/30 and 12/30 for the first model. This sample is too small and narrow to predict reliability on arbitrary uploads. The [evaluation log](docs/EVALUATION.md) includes the mistakes and [model review](docs/MODEL_REVIEW.md) records the selection rule.

## What works in this local release

- Select or drop one to eight JPEG, PNG, or WebP files; preview each before submitting.
- Choose V3 E2, Community Forensics, or both for a batch; both are selected by default. Analyze files one at a time and inspect each model's suggestion separately, including disagreements.
- See processing, result, or individual model error state; retry failures and export results as CSV.
- The API checks actual image bytes, dimensions, corruption, and a 10 MB limit. It returns each selected model's score, threshold, version, and timing. One model can still return a result if the other fails.
- Open **Inspect model inputs** on a completed result to see an on-demand original display copy and the pixel views used by each successful model pipeline. V3 E2 has separate FFT and MobileNet views. The previews stop before tensor normalization and do not explain a decision.
- Check **Content Credentials** on the original uploaded file with the official C2PA browser SDK. The separate panel reports validation and signer trust, creation claims, and conflicts with model suggestions. The local prototype uses a bundled trust-list snapshot; its [validation record and remaining checks](docs/C2PA_FEASIBILITY.md) are documented.
- Download a per-image JSON case report or open a print-friendly report preview and use **Print or save as PDF**. The report records the original byte hash, dimensions, analysis times, model/recipe revisions, separate results or errors, and limitations. It omits the original image; keep the exact file if you need to reproduce the case.
- Explore the **local review draft** challenge gallery: eight curated cases with private in-tab guesses, source and rights records, each pinned model's suggestion, and filters for documented origin, disagreement, and a model conflict. These selected examples are not an accuracy sample. The exact cases, labels, and reveal wording await owner approval before publication.
- Guest and unsaved analyses stay temporary in browser/process memory. Opt-in private history works locally behind `IOS_LOCAL_TEST_AUTH=1` (off by default), using ignored `.local/history` storage. The [local verification record](docs/HISTORY_LOCAL_VERIFICATION_2026-10-25.md) covers the save, retrieval, ownership, quota, deletion, expiry, browser, and offline model checks. This adds no Cognito integration or AWS storage.

The eight-image cap is a provisional local guard. It has not been validated as a safe public-server capacity limit; measure peak RAM and request timing before raising or relying on it for hosting.

Next, finish the remaining post-redesign browser checks and Content Credentials cases, then measure runtime resources for AWS planning. The optional robustness lab was skipped by the owner. The [current milestone status](docs/NEXT_IMPLEMENTATION_PLAN.md) and [local history design](docs/PRIVATE_HISTORY_IMPLEMENTATION_PLAN.md) distinguish completed local work from hosted work. Local test sign-in is off by default; Cognito, AWS storage, and public deployment are not implemented. The [researched product opportunities](docs/PRODUCT_OPPORTUNITIES.md) are proposals rather than implemented features.

History is opt-in per analysis: guests remain unsaved, and a signed-in local test user must turn on saving to retain the exact original file and result for 30 days. Limits are 10 items or 50 MB per test identity and 500 MB combined saved originals across the local installation. Deleted and expired items become unreadable immediately; the local cleanup sweep removes remaining files. These are local safeguards, not cloud capacity or security guarantees.

The gallery's [draft manifest](docs/GALLERY_MANIFEST.json), [public AI-image source record](docs/GALLERY_PUBLIC_AI_SOURCES.md), and [USGS camera-photo source record](docs/GALLERY_CAMERA_SOURCES.md) give the sources, display rights, edits, and hashes. The app serves optimized display copies from `frontend/public/gallery/candidates/`; acquired camera source copies remain ignored under `.local/`. Each displayed suggestion was recorded by running the actual pinned `/api/analyze/compare` path on the display JPEG. The AI cases were selected from public COCOXGEN images after viewing model output, and that source family also contributed to V3 E2 development; this is a curated demonstration, not an accuracy estimate. **Do not deploy the current frontend bundle or gallery assets publicly before the owner approves these exact cases and reveal wording.**

## Run on Windows

Prerequisites: Python 3.12, Node.js with npm, Git, internet access on the first load of either model, and enough RAM for ONNX Runtime plus PyTorch/TorchVision. Run these commands in PowerShell from this folder.

**Terminal 1: API**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-lock.txt
$env:PYTHONPATH = "backend"
$env:HF_HOME = (Join-Path (Get-Location) "model-cache")
Remove-Item Env:IOS_LOCAL_TEST_AUTH -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

For ordinary guest-only use, leave `IOS_LOCAL_TEST_AUTH` unset. The local
test sign-in switch is only for loopback development; it does not connect to
Cognito or create a hosted account. The API startup above clears the variable
for guest-only use. To switch to history review, stop the API first, then run
these commands in Terminal 1 instead of the default startup line:

```powershell
$env:IOS_LOCAL_TEST_AUTH = "1"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

With the switch enabled, the header exposes the **Alice** and **Bob** local
test identities; these are disposable test fixtures, not real accounts.

To return to the default disabled mode before restarting uvicorn, run:

```powershell
Remove-Item Env:IOS_LOCAL_TEST_AUTH -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

**Terminal 2: interface**

```powershell
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite (usually `http://127.0.0.1:5173`; it may use the next port if that one is busy). The first analysis with each model may download its pinned weights into this project's ignored cache and take longer. Later analyses reuse loaded models. To stop, press Ctrl+C in both terminals.

On Windows, stop a running Vite server before running `npm ci` again; it can keep `esbuild.exe` open and prevent npm from replacing that file.

The Python lockfile records the direct and transitive package versions used on Windows with Python 3.12. `backend/requirements.txt` and `backend/requirements-dev.txt` document the top-level packages to update when deliberately refreshing dependencies; `frontend/package-lock.json` pins the JavaScript dependency tree.

If the first analysis reports a model error, check the API terminal and network access to Hugging Face or TorchVision's official weight download. `GET http://127.0.0.1:8001/api/health` checks the API process, **not** whether either model has downloaded.

The input inspector re-sends the selected file to the same local API only when opened. Closing it discards its in-browser display data. The JSON and printable reports are generated in the browser; the API does not store report files. An opted-in History item stores the server result snapshot and exact original bytes, so the report can be rebuilt later. The report preview is keyboard accessible, closes with Escape, and prints without the rest of the app. Match a report to the original bytes by SHA-256, not by filename.

## Reading a result

Each model produces an AI score, and its displayed real score is `1 - AI score`. **E2 flags AI at 50%; Community Forensics uses its published 65% cutoff.** The numbers come from different training and calibration histories, so a larger score from one model does not make it more reliable than the other. For example, Community Forensics can show a 60% AI score while suggesting “Real” because 60% is below its cutoff. Neither score is a verified probability of origin for your upload. Keep the image's source information alongside the suggestions.

## Checks

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe scripts\verify_gallery_manifest.py
cd frontend
npm run format:check
npm run build
```

The API tests use stub detectors to verify validation and response shape without downloading weights. The inspector tests verify each model's selected views and the exact pre-normalization input path, including a MobileNet tensor parity check. E2 has a separate parity check against its original locked inference pipeline; that check verifies the port, not accuracy. The recorded 60-image check ran the Community Forensics ONNX weights through the app. Before claiming one model performs better, compare both on the same new, known-origin images under the [fixed comparison protocol](docs/DUAL_MODEL_EVALUATION.md).

A [public 12-image paired pilot](docs/PUBLIC_PILOT_2026-10-24.md) now exercises both real inference paths and records their mistakes on the same files. It is deliberately labeled diagnostic: all generated samples come from one generator, all real photos from one source, and model-training overlap is unknown. Its [manifest](docs/PUBLIC_PILOT_MANIFEST.csv), [runner](scripts/compare_models.py), and per-image JSON reports make the result reproducible without committing the images.

The older `scripts\sanity_check.py` checks **Community Forensics only**. Give it a private CSV with `path,known_origin,source,note` columns and run `.\.venv\Scripts\python.exe scripts\sanity_check.py path\to\manifest.csv --output path\to\new-report.json`. It refuses to overwrite a report and records image hashes, that model's two class scores, its revision, and load/inference timing. This is an implementation check, not a comparison or accuracy estimate. For a two-model inspection, select both in the app and export its per-model CSV; the fixed protocol for a new head-to-head evaluation is in `docs/DUAL_MODEL_EVALUATION.md`.

## Architecture in plain language

```text
Browser (React) ──image + model choice──> FastAPI ──> image validation
    ▲                                      ├──> V3 E2: FFT + MobileNet + fusion head
    └──── separate results and versions ◀─┴──> Community Forensics: pinned ONNX
Optional local test sign-in + save ──────────> SQLite record + private original
```

The browser is the screen. FastAPI checks files and runs the selected pretrained and saved inference pipelines; it does not train either model during a request. The current batch sends files one after another. Only an explicitly saved analysis writes to the local SQLite database and ignored `.local/history` original-file directory. There is no queue or cloud service yet. The ML Project folder is not required at runtime. Both models must be measured together before designing an AWS worker.

## Cloud roadmap and cost gate

AWS is the planned deployment target; cloud infrastructure is **not deployed**. First measure cold load, peak memory, and inference time with E2, Community Forensics, and both loaded on this PC. Then choose AWS compute and supporting services that fit those measurements. A possible design is private S3 uploads, SQS jobs, a model worker, a result store, and logs; the exact services are not selected yet. Review an estimate, budget alert, and teardown steps before provisioning paid resources. A static frontend alone cannot execute these Python models.

## Documentation map

- [Current milestone status and next gates](docs/NEXT_IMPLEMENTATION_PLAN.md)
- [Local history behavior and verification](docs/PRIVATE_HISTORY_IMPLEMENTATION_PLAN.md) · [test record](docs/HISTORY_LOCAL_VERIFICATION_2026-10-25.md)
- [AWS implementation plan](docs/AWS_IMPLEMENTATION_PLAN.md) · [deployment route and release checks](docs/DEPLOYMENT.md)
- [Screen plan](docs/WIREFRAMES.md) · [redesign review](docs/SITE_REDESIGN_REVIEW.md)
- [Evaluation log](docs/EVALUATION.md) · [Content Credentials checks](docs/C2PA_FEASIBILITY.md) · [gallery source records](docs/GALLERY_MANIFEST.json)

## Limits

Both models may misclassify unfamiliar generators, edited or compressed images, screenshots, and real images unlike their training data. E2's historical 92% final result and Community Forensics' 85% app screening result came from **different** samples and cannot rank the models. E2's saved out-of-source diagnostics were weaker than its within-source final result. Their scores are not verified probabilities of authenticity for arbitrary uploads. Neither model can establish provenance. The local server is bound to `127.0.0.1` and has no production authentication or distributed rate limiting; do not expose it publicly as is.
