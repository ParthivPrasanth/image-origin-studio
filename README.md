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
- Uploaded bytes and results stay in process/browser memory. There is no server database, cloud upload, account, or durable history yet.

The eight-image cap is a provisional local guard. It has not been validated as a safe public-server capacity limit; measure peak RAM and request timing before raising or relying on it for hosting.

Next product stages are a licensed, known-origin sample gallery that exposes incorrect predictions, then optional accounts with private, deletable history. The queue and cloud architecture follow measured local resource use and the cost review described below. The [researched product opportunities](docs/PRODUCT_OPPORTUNITIES.md) propose an evidence workbench, input-view inspector, robustness lab, and provenance panel for review before a major direction is chosen.

## Run on Windows

Prerequisites: Python 3.12, Node.js with npm, Git, internet access on the first load of either model, and enough RAM for ONNX Runtime plus PyTorch/TorchVision. Run these commands in PowerShell from this folder.

**Terminal 1: API**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-lock.txt
$env:PYTHONPATH = "backend"
$env:HF_HOME = (Join-Path (Get-Location) "model-cache")
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

## Reading a result

Each model produces an AI score, and its displayed real score is `1 - AI score`. **E2 flags AI at 50%; Community Forensics uses its published 65% cutoff.** The numbers come from different training and calibration histories, so a larger score from one model does not make it more reliable than the other. For example, Community Forensics can show a 60% AI score while suggesting “Real” because 60% is below its cutoff. Neither score is a verified probability of origin for your upload. Keep the image's source information alongside the suggestions.

## Checks

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m ruff check backend
cd frontend
npm run format:check
npm run build
```

The API tests use stub detectors to verify validation and response shape without downloading weights. E2 has a separate parity check against its original locked inference pipeline; that check verifies the port, not accuracy. The recorded 60-image check ran the Community Forensics ONNX weights through the app. Before claiming one model performs better, compare both on the same new, known-origin images under the [fixed comparison protocol](docs/DUAL_MODEL_EVALUATION.md).

A [public 12-image paired pilot](docs/PUBLIC_PILOT_2026-10-24.md) now exercises both real inference paths and records their mistakes on the same files. It is deliberately labeled diagnostic: all generated samples come from one generator, all real photos from one source, and model-training overlap is unknown. Its [manifest](docs/PUBLIC_PILOT_MANIFEST.csv), [runner](scripts/compare_models.py), and per-image JSON reports make the result reproducible without committing the images.

The older `scripts\sanity_check.py` checks **Community Forensics only**. Give it a private CSV with `path,known_origin,source,note` columns and run `.\.venv\Scripts\python.exe scripts\sanity_check.py path\to\manifest.csv --output path\to\new-report.json`. It refuses to overwrite a report and records image hashes, that model's two class scores, its revision, and load/inference timing. This is an implementation check, not a comparison or accuracy estimate. For a two-model inspection, select both in the app and export its per-model CSV; the fixed protocol for a new head-to-head evaluation is in `docs/DUAL_MODEL_EVALUATION.md`.

## Architecture in plain language

```text
Browser (React) ──image + model choice──> FastAPI ──> image validation
    ▲                                      ├──> V3 E2: FFT + MobileNet + fusion head
    └──── separate results and versions ◀─┴──> Community Forensics: pinned ONNX
```

The browser is the screen. FastAPI checks files and runs the selected pretrained and saved inference pipelines; it does not train either model during a request. The current batch sends files one after another, so there is no queue or cloud service yet. The ML Project folder is not required at runtime. Both models must be measured together before designing an AWS worker.

## Cloud roadmap and cost gate

AWS is the planned deployment target; cloud infrastructure is **not deployed**. First measure cold load, peak memory, and inference time with E2, Community Forensics, and both loaded on this PC. Then choose AWS compute and supporting services that fit those measurements. A possible design is private S3 uploads, SQS jobs, a model worker, a result store, and logs; the exact services are not selected yet. Review an estimate, budget alert, and teardown steps before provisioning paid resources. A static frontend alone cannot execute these Python models.

See [deployment guide](docs/DEPLOYMENT.md), [screen plan](docs/WIREFRAMES.md), and [evaluation log](docs/EVALUATION.md).

## Limits

Both models may misclassify unfamiliar generators, edited or compressed images, screenshots, and real images unlike their training data. E2's historical 92% final result and Community Forensics' 85% app screening result came from **different** samples and cannot rank the models. E2's saved out-of-source diagnostics were weaker than its within-source final result. Their scores are not verified probabilities of authenticity for arbitrary uploads. Neither model can establish provenance. The local server is bound to `127.0.0.1` and has no production authentication or distributed rate limiting; do not expose it publicly as is.
