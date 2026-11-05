<h1 align="center">Image Origin Studio</h1>

Image Origin Studio lets you look more closely at an image before deciding what to make of it. Upload a file, compare two detectors, inspect the pixels each one receives, and check for embedded Content Credentials. If an analysis is useful, you can save it to private History.

This app grew out of a separate image-detection ML project. The **V3 E2** model in the app uses a fusion head trained in that project; **Community Forensics** is a pinned external model used alongside it. Their answers are shown separately, including when they disagree or make a mistake.

[Live site](https://35.154.237.144/) · [Run locally](#run-it-locally) · [How it works](#how-it-works) · [Documentation](docs/README.md)

![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white) ![React 19](https://img.shields.io/badge/React-19-149ECA?logo=react&logoColor=white) ![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white) ![AWS](https://img.shields.io/badge/Hosted%20on-AWS-232F3E?logo=amazonwebservices&logoColor=white) ![License: MIT](https://img.shields.io/badge/License-MIT-2F6D68)

> **A screening tool, not a provenance verdict.** Model scores are suggestions from fixed decision rules. A C2PA credential is a separate signed claim about a file. Neither a model score nor the absence of a credential proves how an image was made.

## Explore the product

| Analyze | Gallery | History |
| --- | --- | --- |
| Upload up to eight images and compare **V3 E2**, **Community Forensics**, or both. See each model's score, cutoff, version, timing, and errors independently. | Guess the origin of eight source-documented cases before revealing the source record and both model suggestions. The cases include disagreements and mistakes. | Sign in with Cognito, explicitly opt in to saving an analysis, reopen the exact original and result snapshot, or delete saved items. |

The analysis screen also offers an on-demand view of each model's input image, a browser-side Content Credentials check against the **original bytes**, CSV export, and per-image JSON or print-friendly case reports. The gallery is a curated demonstration, **not an accuracy test**. Its [source manifest](docs/GALLERY_MANIFEST.json) records provenance, rights, transformations, hashes, and pinned model runs.

The gallery has eight cases. Each has a traceable source and credit, and some show the detectors getting it wrong. The app leaves those mistakes visible beside the source records.

| Documented camera photograph | Generated image |
| :---: | :---: |
| ![USGS waterfall photograph used in the source-documented gallery](frontend/public/gallery/candidates/waterfall-display.jpg) | ![Generated skier image used in the source-documented gallery](frontend/public/gallery/candidates/cocoxgen-000000445602-sdxl-long-display.jpg) |
| [USGS source and credit](docs/GALLERY_CAMERA_SOURCES.md) | [COCOXGEN source and CC BY 4.0 credit](docs/GALLERY_PUBLIC_AI_SOURCES.md) |

## Live deployment

Image Origin Studio went live on **29 October 2026** at **[https://35.154.237.144/](https://35.154.237.144/)**. The public HTTPS site and `/api/health` were reachable; model analysis, Cognito sign-in, and an image saved to History were also confirmed. The address is an Elastic IP rather than a custom domain. Live availability may change if the trial is stopped or the IP is released.

The frontend redesign in this repository was reviewed locally on **4 November 2026**. It has not yet been installed on the public AWS host; the live site may still show the earlier interface. See the [local redesign verification record](docs/archive/FRONTEND_REDESIGN_IMPLEMENTATION_2026-11-05.md).

The deployment runs in AWS **Asia Pacific (Mumbai), `ap-south-1`**: one Ubuntu EC2 host serves the React build through Nginx and HTTPS; Nginx proxies `/api` to a Dockerized FastAPI process bound to loopback. Cognito provides hosted sign-in. Explicitly saved originals go to a private S3 bucket and History metadata and quotas go to DynamoDB. An EC2 instance role supplies AWS access without static keys on the host. The [deployment guide](docs/DEPLOYMENT.md) explains the topology, settings, checks, and operating tasks.

This is a small public deployment, not a claim of production-scale reliability. Successful sign-in and saving have been confirmed; a completed second-account isolation test, a verified budget alert, and inspection of the installed certificate-renewal schedule have not been recorded. Those checks are tracked in the [deployment guide](docs/DEPLOYMENT.md#remaining-release-and-operations-checks).

## How it works

```mermaid
flowchart LR
    B[Browser · React] -->|HTTPS| N[Nginx · EC2]
    N -->|/api · loopback| A[FastAPI · Docker]
    A --> V[V3 E2 · FFT + MobileNetV3 + fusion head]
    A --> C[Community Forensics · ONNX]
    B -->|Optional sign-in| I[Amazon Cognito]
    A -->|Opt-in originals| S[(Private S3)]
    A -->|Opt-in History records| D[(DynamoDB)]
```

The browser sends each selected image to the API. The API validates its bytes, format, dimensions, and size, then runs the requested model pipelines one at a time. If one model fails, the other can still return its result. No training occurs during a request. The frontend generates reports and performs the C2PA check separately; it does not combine the two model scores into one verdict. [Architecture and data flow →](docs/ARCHITECTURE.md)

| Model | What runs | AI flagging rule | Ownership |
| --- | --- | --- | --- |
| **V3 E2** | 64 FFT features plus 848 features from a frozen, ImageNet-pretrained MobileNetV3-Small backbone; an owner-trained fusion head and fitted scalers are packaged in [`v3_e2.npz`](backend/artifacts/README.md). | AI score **≥ 0.50** | Owner-trained head; TorchVision pretrained backbone is downloaded separately and hash-checked. |
| **Community Forensics** | The pinned [Thermostatic ONNX baseline](https://huggingface.co/Thermostatic/community-forensics-frontier-detector-2026-08), revision `16db135220b318d811b207db576d90368980b595`. | AI score **≥ 0.65**, following its published cutoff. | External model, credited under its own MIT terms; weights are downloaded and hash-checked. |

### How V3 E2 was developed

The ML work began with a practical question: could frequency features and a frozen CNN complement each other? The first experiment compared a 16-feature Fourier baseline, features from MobileNetV3-Small, and a logistic-regression hybrid on a small community Tiny-GenImage sample. The hybrid led validation, but that lead did not clearly hold on the reserved test groups. The Fourier model in particular recognized only 9 of 100 Wukong-generated images in one test group. That failure made it hard to justify a detector from one validation score.

V2 moved to a richer description of each image: **64 frequency features** from the Fourier spectrum and **848 spatial features** from several points in MobileNetV3-Small. A small learned fusion head combined them. It led the development comparison, but on the locked final group it tied a simpler reference on the mean of clean and JPEG-quality-50 views. Both models also falsely flagged many compressed real photos. V3 tested whether showing both classes compressed images during training would reduce that sensitivity.

V3 kept the same feature extractors and fusion head for E0 and E2. **E0** trained on clean images. **E2** saw a clean or JPEG-50 view of each training image, chosen anew each epoch, with the same choice rule for real and generated images. The frequency and spatial scalers were fitted on training data only; MobileNet's ImageNet weights stayed frozen. Only the small fusion head was trained for this app model.

```text
Image → orientation correction → center crop → 224 × 224 RGB
      ├─ Fourier spectrum → 64 features → scaler → 32-unit branch
      └─ frozen MobileNetV3-Small → 848 features → scaler → 64-unit branch
                                      ↓
                          concatenate 96 values
                                      ↓
                         32-unit layer → AI score
```

The V3 experiment used 1,000 training images, 200 development images, and a separate 200-image final group, each balanced between real and generated images. E2 was selected on development results before that final group was scored. On the final group it reached **92% balanced accuracy** on both clean and JPEG-50 views; E0, which used the same architecture without the mixed-view training, reached **87% clean** and **83% JPEG-50**. The clean and JPEG views are two versions of the same final images, not two independent test sets.

That result supports the training change **within the COCOXGEN/COCO source family used for V3**. It is not a measured accuracy for arbitrary uploads. Original file format, dimensions, content, and generator remain linked to class in that dataset, and later checks on older out-of-source groups were much weaker. The final group has already been viewed and is closed to further tuning. The separate ML Project retains the training scripts, split manifests, candidate comparisons, and locked evaluation; this app packages only the [inference artifact and fitted scalers](backend/artifacts/README.md), with no training data or runtime dependency on that project.

The two app models also have different training histories and preprocessing. Their displayed scores are **not calibrated probabilities for arbitrary uploads**, and a higher score from one model does not rank it above the other. Community Forensics' historical **85%** app screening result used a different image set from V3 E2's **92%** final result, so those percentages cannot rank the two models. A [12-image paired pilot](docs/evaluation/PUBLIC_PILOT_2026-10-24.md) shows concrete errors on the same files but is too narrow for a general performance claim. See the [evaluation guide](docs/README.md#models-and-evaluation) for methods and limits.

## Privacy and saved History

Guest use needs no account. Every upload reaches the hosted API for analysis, but the application does **not add guest or unsaved analyses to History**. A signed-in user must select **Save this analysis to my history** for each batch. Saved items contain the unmodified original, including any embedded metadata, and a snapshot of the result. The current rules are **30-day expiry**, **10 items or 50 MiB per identity**, and **500 MiB of saved originals across all identities**. Deletion and expiry make an item unreadable before background cleanup removes its storage objects.

The local development mode uses SQLite and ignored files; hosted mode uses S3 and DynamoDB. Local test identities are deliberately loopback-only and disabled by default. For details, including what is and is not verified on the live host, read [Architecture and data flow](docs/ARCHITECTURE.md#history-and-data-lifecycle) and the [deployment guide](docs/DEPLOYMENT.md).

## Run it locally

**Prerequisites:** Windows PowerShell, Python 3.12, Node.js with npm, and internet access for the first download of each model's pinned weights. Start in the repository root. The Python lockfile targets Python 3.12; the frontend lockfile pins the npm tree.

**Terminal 1 — API**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-lock.txt
$env:PYTHONPATH = "backend"
$env:HF_HOME = (Join-Path (Get-Location) "model-cache")
Remove-Item Env:IOS_LOCAL_TEST_AUTH -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

**Terminal 2 — frontend**

```powershell
cd frontend
npm ci
npm run dev
```

Open the URL Vite prints, usually `http://127.0.0.1:5173`. Its development proxy sends `/api` requests to `http://127.0.0.1:8001`. The first real analysis may take longer while weights download and load. Press **Ctrl+C** in both terminals to stop.

Local History can be reviewed with disposable Alice/Bob identities by restarting the API with `$env:IOS_LOCAL_TEST_AUTH = "1"` before the `uvicorn` command. This switch works only on loopback and is **not** a hosted account system. Keep it unset for ordinary local use. See [Local History verification](docs/archive/HISTORY_LOCAL_VERIFICATION_2026-10-25.md) and [Developer checks](#developer-checks).

## Developer checks

From the repository root after installing the dependencies above:

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe scripts\verify_gallery_manifest.py
cd frontend
npm run format:check
npm run build
```

API tests use stub detectors for fast validation and route checks. They do not establish real-model accuracy. For an actual pinned-model smoke run and container checks, follow [Architecture and data flow](docs/ARCHITECTURE.md#verification) and the [dated AWS readiness record](docs/archive/AWS_READINESS_2026-10-26.md). The current cloud adapter has unit tests, while the [live-host checklist](docs/DEPLOYMENT.md#remaining-release-and-operations-checks) tracks checks that still need direct evidence.

## Repository map

```text
backend/    FastAPI, inference pipelines, local and AWS History, tests, model artifact
frontend/   React UI, browser-side C2PA and reports, curated gallery assets
infra/      Parameterized Nginx and IAM deployment templates
scripts/    Packaging, parity, gallery, and measurement utilities
docs/       Current guides, model evaluation, source records, and archived project notes
output/     Historical local review captures and example report artifacts
```

Start at the [documentation index](docs/README.md) for the current architecture, deployment, evaluation, source credits, and dated project records.

## License and credits

The project-owned application code, documentation, and packaged V3 E2 fusion artifact are released under the [MIT License](LICENSE), as chosen by the owner. The downloaded TorchVision backbone and Community Forensics weights remain under their upstream terms and are **not** relicensed by this repository. Gallery images retain their separate source rights and attribution; see [third-party notices](THIRD_PARTY_NOTICES.md) and the [gallery source records](docs/GALLERY_MANIFEST.json).
