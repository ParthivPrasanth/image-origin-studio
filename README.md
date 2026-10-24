# Image Origin Studio

A local web app for exploring a credited image classification model. This is a **new project and Git repository**. It does not import the earlier CCD detector or claim that its DINOv2/FFT architecture is used here.

The backend uses [jacoballessio/ai-image-detect-distilled](https://huggingface.co/jacoballessio/ai-image-detect-distilled) (MIT license), pinned to commit `4098d40c873a2e38404ea378a8284f33125bd90c`. Its published configuration maps class `0` to `fake` and class `1` to `real`. The model and its supplied image processor load once per Python process. The author's model card reports 74% validation accuracy and 72% on a custom set; these are the author's figures, not measurements of this app. A score is not proof of image origin.

## What works in this local release

- Select or drop one to eight JPEG, PNG, or WebP files; preview each before submitting.
- Analyze files one at a time in the batch; see processing, result, or individual error state; retry errors and export results as CSV.
- The API checks actual image bytes, dimensions, corruption, and a 10 MB limit. It returns both model scores and the exact model revision.
- Uploaded bytes and results stay in process/browser memory. There is no server database, cloud upload, account, or durable history yet.

The eight-image cap is a provisional local guard. It has not been validated as a safe public-server capacity limit; measure peak RAM and request timing before raising or relying on it for hosting.

Next product stages are a licensed, known-origin sample gallery that exposes incorrect predictions, then optional accounts with private, deletable history. The queue and cloud architecture follow measured local resource use and the cost review described below.

## Run on Windows

Prerequisites: Python 3.12, Node.js with npm, Git, internet access on the first model load, and enough RAM for PyTorch plus the model. Run these commands in PowerShell from this folder.

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

The Python lockfile records the direct and transitive package versions verified on Windows with Python 3.12. `backend/requirements.txt` and `backend/requirements-dev.txt` document the top-level packages to update when deliberately refreshing dependencies; `frontend/package-lock.json` pins the JavaScript dependency tree.

If the first analysis reports a model error, check that the Python terminal can reach Hugging Face and that the pinned revision is available. `GET http://127.0.0.1:8001/api/health` checks the API process, **not** whether the model has downloaded.

## Checks

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m ruff check backend
cd frontend
npm run format:check
npm run build
```

The API tests use a stub detector so they can verify validation and response shape without downloading model weights. A separate manual model sanity check with known-origin images is still required before interpreting real predictions. Record sources and results in `docs/EVALUATION.md`; do not use earlier viewed test results to tune this model.

For that smoke check, make a private CSV with `path,known_origin,source,note` columns and run `.\.venv\Scripts\python.exe scripts\sanity_check.py path\to\manifest.csv --output path\to\new-report.json`. The script refuses to overwrite an existing report and records image hashes, both scores, the model revision, and load/inference timing. Its output is an implementation check, not an accuracy estimate.

## Architecture in plain language

```text
Browser (React) ──image POST──> FastAPI process ──> image validation
    ▲                                      │
    └──── scores and model revision ◀─────┴── pinned ViT + processor
```

The browser is the screen. FastAPI is the local server that checks files and runs Python. The model is the classifier; this code does not train it. The current batch simply sends files one after another, so no queue or cloud service is needed yet. This makes correctness and resource use measurable before designing a worker system.

## Cloud roadmap and cost gate

Cloud infrastructure is **planned, not deployed**. First measure cold model load time, peak memory, and image inference time on this PC and on a candidate host. Then choose a provider that fits those measurements. If AWS remains the best fit, a possible later design is private S3 uploads, SQS jobs, a model worker, a result store, and logs. Those services can cost money and must be reviewed with an estimate, budget alert, and teardown steps before provisioning. A static frontend alone cannot execute this Python model.

See [deployment guide](docs/DEPLOYMENT.md), [screen plan](docs/WIREFRAMES.md), and [evaluation log](docs/EVALUATION.md).

## Limits

This model may misclassify unfamiliar generators, edited or compressed images, screenshots, and real images unlike its training data. The two numbers are relative model scores, not calibrated probabilities of authenticity. Neither this app nor the model can establish provenance. The local server is bound to `127.0.0.1` and has no production authentication or distributed rate limiting; do not expose it publicly as is.
