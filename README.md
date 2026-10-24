# Image Origin Studio

A local web app for exploring a credited image classification model. This is a **new project and Git repository**. It does not import the earlier CCD detector or claim that its DINOv2/FFT architecture is used here.

The backend uses [Thermostatic/community-forensics-frontier-detector-2026-08](https://huggingface.co/Thermostatic/community-forensics-frontier-detector-2026-08) (MIT license), pinned to commit `16db135220b318d811b207db576d90368980b595`. Its 44 MB ONNX weights are checked against the published SHA-256 before loading. The app follows the model card's RGB resize, center crop, normalization, calibration, and published 65% AI flagging cutoff. This is a whole-image **experimental screening model**, not a provenance test.

The first model failed badly on a small folder of user-supplied images, particularly those provisionally labeled real. A separate 60-image, dataset-labeled check favored this replacement: 25/30 real and 26/30 generated images correct, versus 18/30 and 12/30 for the first model. This sample is too small and narrow to predict reliability on arbitrary uploads. The [evaluation log](docs/EVALUATION.md) includes the mistakes and [model review](docs/MODEL_REVIEW.md) records the selection rule.

## What works in this local release

- Select or drop one to eight JPEG, PNG, or WebP files; preview each before submitting.
- Analyze files one at a time in the batch; see processing, result, or individual error state; retry errors and export results as CSV.
- The API checks actual image bytes, dimensions, corruption, and a 10 MB limit. It returns the AI score, its complement, the published cutoff, and the exact model revision.
- Uploaded bytes and results stay in process/browser memory. There is no server database, cloud upload, account, or durable history yet.

The eight-image cap is a provisional local guard. It has not been validated as a safe public-server capacity limit; measure peak RAM and request timing before raising or relying on it for hosting.

Next product stages are a licensed, known-origin sample gallery that exposes incorrect predictions, then optional accounts with private, deletable history. The queue and cloud architecture follow measured local resource use and the cost review described below.

## Run on Windows

Prerequisites: Python 3.12, Node.js with npm, Git, internet access on the first model load, and enough RAM for ONNX Runtime plus the model. Run these commands in PowerShell from this folder.

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

Open the local URL printed by Vite (usually `http://127.0.0.1:5173`; it may use the next port if that one is busy). The first analysis downloads the pinned model into this project's ignored `model-cache/` directory and can take longer. Later analyses reuse the loaded model. To stop, press Ctrl+C in both terminals.

The Python lockfile records the direct and transitive package versions used on Windows with Python 3.12. `backend/requirements.txt` and `backend/requirements-dev.txt` document the top-level packages to update when deliberately refreshing dependencies; `frontend/package-lock.json` pins the JavaScript dependency tree.

If the first analysis reports a model error, check that the Python terminal can reach Hugging Face and that the pinned revision is available. `GET http://127.0.0.1:8001/api/health` checks the API process, **not** whether the model has downloaded.

## Reading a result

The model produces one AI score, and the displayed real score is `1 - AI score`. Its author fixed the AI flagging cutoff at **65%**. For example, an AI score of 60% appears with a “Real” suggestion because it is below that cutoff. The score is calibrated on the author's development data and should not be read as a 60% chance that your image is AI-generated. Keep the image's source information alongside any model result.

## Checks

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m ruff check backend
cd frontend
npm run format:check
npm run build
```

The API tests use a stub detector so they can verify validation and response shape without downloading model weights. The recorded 60-image check ran the pinned ONNX weights through the app. Before interpreting results from new types of images, gather verified origins and compare errors by source; do not use the already viewed sample to tune this model.

For that smoke check, make a private CSV with `path,known_origin,source,note` columns and run `.\.venv\Scripts\python.exe scripts\sanity_check.py path\to\manifest.csv --output path\to\new-report.json`. The script refuses to overwrite an existing report and records image hashes, both scores, the model revision, and load/inference timing. Its output is an implementation check, not an accuracy estimate.

## Architecture in plain language

```text
Browser (React) ──image POST──> FastAPI process ──> image validation
    ▲                                      │
    └──── scores and model revision ◀─────┴── pinned ONNX detector
```

The browser is the screen. FastAPI is the local server that checks files and runs Python. The model is the classifier; this code does not train it. The current batch simply sends files one after another, so no queue or cloud service is needed yet. This makes correctness and resource use measurable before designing a worker system.

## Cloud roadmap and cost gate

Cloud infrastructure is **planned, not deployed**. First measure cold model load time, peak memory, and image inference time on this PC and on a candidate host. Then choose a provider that fits those measurements. If AWS remains the best fit, a possible later design is private S3 uploads, SQS jobs, a model worker, a result store, and logs. Those services can cost money and must be reviewed with an estimate, budget alert, and teardown steps before provisioning. A static frontend alone cannot execute this Python model.

See [deployment guide](docs/DEPLOYMENT.md), [screen plan](docs/WIREFRAMES.md), and [evaluation log](docs/EVALUATION.md).

## Limits

This model may misclassify unfamiliar generators, edited or compressed images, screenshots, and real images unlike its training data. Its AI score uses calibration fitted on the model author's development data; the real score is `1 - AI score`. These numbers are not verified probabilities of authenticity for your uploads. The model card reports weaknesses for tiny synthetic regions and severe low-resolution edits. Neither this app nor the model can establish provenance. The local server is bound to `127.0.0.1` and has no production authentication or distributed rate limiting; do not expose it publicly as is.
