# AWS readiness checkpoint — 26 October 2026

> **Dated local checkpoint.** “No AWS resource” below describes 26 October.
> The owner deployed the public site on 29 October. For current status and
> live-host checks, see [Deployment and operations](../DEPLOYMENT.md).

This is a local implementation record for the [AWS plan](AWS_IMPLEMENTATION_PLAN.md).
No AWS resource was created. The baseline commit was `d5818ab`; the script,
container definition, and this record are subsequent working-tree changes.

## Phase 0: local release sweep

| Check | Observed result |
| --- | --- |
| Backend tests | 37 passed, 2 warnings. The warnings concern Starlette's test client and the intentional pixel-limit image. |
| Backend and measurement-script Ruff | Passed. |
| Frontend Prettier and production build | Passed. |
| Guest browser, desktop | Eight checked-in gallery display JPEGs queued and analyzed sequentially with both real pinned models; all eight returned both model results. Export CSV appeared. Saving was off. |
| Phone browser, 390 × 844 | Analyze results, model detail rows, Content Credentials, and the input inspector remained readable without horizontal clipping. |
| Tablet browser, 768 × 1024 | Gallery grid and the then-current draft banner rendered clearly. The banner was removed after owner publication review. |
| Input inspector | Original display copy, V3 E2 FFT and MobileNet views, and Community Forensics crop appeared with distinct recipes. |
| Content Credentials | An unsigned gallery JPEG displayed “No Content Credential found” and said origin remains unknown. |
| Local History | Alice opted in before analysis, retrieved the exact original with matching SHA-256, and opened the saved result/report preview. Sign-out hid History; Bob saw an empty account. A [full-page desktop capture](../../output/review/release-sweep-history-desktop.png) records the saved-result screen. |
| Partial model error | The first browser run exposed a Community Forensics error because I launched the API without the documented `HF_HOME` setting and outbound downloads were unavailable. The app kept V3 E2 results visible. Restarting with the README cache setting and `HF_HUB_OFFLINE=1` made all eight two-model comparisons succeed. |

The owner subsequently marked the saved/printed PDF, keyboard-only use, and
gallery publication review as done. These are owner-reported checks, not
independently repeated in this record; the owner considers the gallery ready
for public inclusion. At this first sweep, quota-full, deleted, and expired
History states and browser examples of unsupported C2PA input and
credential/model conflict were still unchecked. Backend tests covered quota,
expiry, ownership, deletion, and partial model errors, but did not replace
those browser observations. The follow-up below closes some of these gaps.
The single Alice test item created for this sweep was deleted through the
localhost API after the screenshot; a follow-up list returned zero items.

### Follow-up release states, 26 October

An isolated localhost API on port 8002 used a disposable History directory;
the browser used a separate Vite server on port 5175. Ten copies of the public
bird gallery image filled Alice's 10-item quota. The full-state explanation
was visible and readable at phone and desktop widths; the
[phone capture](../../output/review/release-sweep-quota-phone.png) shows the
message. A stale item whose
expiry was moved into the past showed a clear unavailable message and
**Refresh History** action. Refresh removed it from the visible list. A
separately deleted item and the expired item both returned HTTP 404 for
metadata and exact-original retrieval. A manual cleanup sweep removed
the expired original. All disposable History files were removed afterward.

The sweep found and repaired a presentation issue: a normal refresh cleared
successful deletion feedback immediately. History now keeps that message while
refreshing the list, explicitly explains a full account quota, refreshes its
quota after Delete all, and lets the user refresh a stale expired/deleted
item. A subsequent headless Chromium run used one disposable public gallery
image saved under local-test Alice. After confirming Delete in the browser,
**The saved image was deleted.** remained visible through automatic list
refresh, the list showed **No saved analyses**, and quota returned to 0 of 10.
The [desktop capture](../../output/review/release-sweep-delete-feedback.png)
records the resulting screen. The disposable data was removed after the check.
Expired items can still count against
quota until the hourly cleanup sweep completes, although they are already
inaccessible and absent from the visible list.

A generated, unsigned WebP passed through the browser's credential checker and
showed **No Content Credential found**. WebP is therefore not an unsupported
format fixture. JPEG, PNG, and WebP are the app's accepted upload formats;
the browser currently has no supported route for submitting a genuinely
unsupported file to this panel. A validated AI-origin credential paired with
a model-real suggestion still needs a real browser fixture and review. The
existing panel logic displays that conflict separately; this observation does
not close that browser gate.

For a controlled conflict UI check, four existing, ignored ImageGen original
PNGs were analyzed locally with V3 E2 and opened from disposable private
History. The signed camping-mug original showed a **trusted** active
AI-generation claim in the browser; the real V3 E2 model suggested
AI-generated for it. The other three originals received V3 E2 real
suggestions, but their browser credential states were invalid, so none is a
real validated-credential/model conflict. A second, localhost-only API run
used the same signed camping-mug bytes and a clearly test-only V3 E2 stub
returning a real suggestion. The [browser capture](../../output/review/release-sweep-c2pa-conflict-stub.png)
shows the trusted claim, separate model suggestion, and visible disagreement
message. The stub's 10% AI score is synthetic UI data, not a model result or
accuracy evidence. The disposable API script and both test History stores
were removed afterward. A conflict fixture using both a validated credential
and a real pinned-model suggestion was not captured in this run. The owner
subsequently confirmed the C2PA edge behavior was checked separately; exact
fixture details were not added to this record.

## Phase 1: cached-weight capacity sample

Reproduce from the repository root on Windows with installed dependencies and
the existing pinned model cache:

```powershell
.\.venv\Scripts\python.exe scripts\measure_runtime.py
```

The raw JSON is written to ignored `.local/runtime-measurements.json`. To keep
another run, pass `--output` with a new path. The script forces offline model
loading and fails if the pinned cache is absent. It starts a fresh Python
process for each model selection, calls the actual FastAPI comparison route
through `TestClient`, measures three warm requests per format, an eight-image
sequential batch, two concurrent requests, the inspector, and one disposable
opt-in History save/retrieve/delete. It records timings and hashes, not model
scores or accuracy.

Machine: Windows 11, AMD Ryzen 7 6800HS, 16 logical CPUs, 15,629 MiB physical
RAM, Python 3.12.4. The source was the checked-in 800 × 531 bird gallery JPEG;
the 2,000 × 2,000 JPEG and PNG/WebP variants were made in memory. The script
records their byte hashes, sizes, package versions, and pinned model hashes.
This is one capacity sample, not a performance guarantee for a cloud host.

| Selection | Cached load | Peak RAM after load | Peak RAM after workload | Warm small-JPEG median, n=3 | Eight-image batch | Two concurrent requests |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V3 E2 | 4.23 s | 314 MiB | 459 MiB | 38 ms | 0.45 s | 0.10 s |
| Community Forensics | 0.73 s | 145 MiB | 368 MiB | 243 ms | 2.04 s | 0.47 s |
| Both | 4.81 s combined | 400 MiB | 721 MiB | 288 ms | 2.48 s | 0.54 s |

The two-request figure is wall time for one small and one large JPEG together,
not a per-request median. Process CPU time, each format's median and slowest
run, inspector timing, and per-request concurrent timings are in the raw JSON.
History with both models took 308 ms including inference; retrieving the
147,681-byte exact original took 13 ms and deletion 15 ms. The disposable
History directory occupied 172,257 bytes after saving and 24,576 bytes after
deletion (the SQLite database remained). The browser's sequential eight-file
batch is consistent with the script's workload, but network overhead and a
different machine will change these numbers.

**Remaining Phase 1 gate:** a controlled uncached model download measurement
and a repeat on actual target hardware are missing. The first Docker request
below included downloads but did not isolate download time from model loading.
The in-process `TestClient` concurrency run does not measure a public HTTP
server's request limits or overload response. The constrained Docker run below
adds a local HTTP sample, but this PC does not reproduce an AWS CPU or network.
These numbers do not justify a final AWS compute size or public concurrency cap.

### Live HTTP concurrency follow-up, 26 October

`scripts/measure_http_concurrency.py` now exercises the real loopback HTTP
server with the checked-in bird JPEG, both pinned models, and no History save.
It stores timings and failures, not scores. Reproduce after starting a local
API or loopback-bound container:

```powershell
.\.venv\Scripts\python.exe scripts\measure_http_concurrency.py --url http://127.0.0.1:8002 --concurrency 1 2 4 --requests-per-level 8 --output .local\http-concurrency.json
```

The isolated Windows API sample returned both model results on all 24 measured
requests, with no HTTP or model errors. Warmup was 3.61 s. The raw local record
is ignored at `.local/release-sweep-next/http-concurrency.json`.

| Simultaneous requests | Count | Median request | Slowest request | Total wall |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 8 | 2.19 s | 2.50 s | 17.54 s |
| 2 | 8 | 2.37 s | 3.05 s | 10.16 s |
| 4 | 8 | 2.68 s | 3.77 s | 6.43 s |

The API process reported 491,048,960 bytes peak working set after the run.
This is a single Windows process sample with cached weights, not a Linux
container memory peak, sustained load result, or AWS CPU equivalent. Docker
was initially unavailable through `PATH` on this execution host. The local
Docker Desktop binary was subsequently found and used for the constrained
Linux container run below. The Windows figures do not set a public
concurrency limit.

### Constrained Linux container HTTP follow-up, 26 October

The existing Docker Desktop image ran locally with `--cpus=2 --memory=2g`,
the previously cached pinned weights, one Uvicorn worker, and port 8003 bound
only to Windows loopback. The same public bird JPEG and both real pinned models
were sent through `/api/analyze/compare`. The command below ran 40 measured
requests at each simultaneous-request level (120 total), following one model
warmup. Raw timings and errors are in ignored
`.local/release-sweep-next/linux-container-concurrency.json`.

```powershell
.\.venv\Scripts\python.exe scripts\measure_http_concurrency.py --url http://127.0.0.1:8003 --concurrency 1 2 4 --requests-per-level 40 --timeout 60 --output .local\release-sweep-next\linux-container-concurrency.json
```

| Simultaneous requests | Count | Median request | Slowest request | Total wall | Failures |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 40 | 0.558 s | 0.809 s | 22.769 s | 0 |
| 2 | 40 | 0.703 s | 1.000 s | 14.439 s | 0 |
| 4 | 40 | 1.285 s | 1.858 s | 13.461 s | 0 |

Warmup took 6.018 s. The container's cgroup `memory.peak` was 914,395,136
bytes (872 MiB); `memory.events` reported zero OOM and zero limit hits.
The CPU quota was 2 cores (`cpu.max`: `200000 100000`); `cpu.stat` recorded
293 throttled periods and 20.18 seconds of throttled time over the container
life, so the CPU limit was exercised. The container was stopped and removed;
the existing Docker image and model-cache volume remain. This is a single
local WSL 2 run on one small JPEG with warm cached weights. It supports a
provisional two-request local operating point, but not an AWS instance size,
public rate limit, or multi-user latency guarantee.

## Phase 2: Linux container build and local verification

The root [Dockerfile](../../Dockerfile) and [.dockerignore](../../.dockerignore) now
define a CPU Python 3.12 backend image with the pinned Python lockfile,
packaged V3 E2 artifact, a non-root runtime user, and writable model caches.
The health check calls `/api/health`, which confirms only that the API process
responds; models still load on first use. Local test sign-in defaults off.
Container-local `/tmp/ios-history` is disposable development storage and is
not a hosted private-history design. Pinned external weights are deliberately
kept out of the image pending measured build/startup and image-size tradeoffs.

The image first built in Debian WSL with Docker Engine. The owner then chose
Docker Desktop on Windows with its WSL 2 backend; the separate Engine and CLI
packages were removed from Debian to avoid conflicting integrations. Docker
Desktop 29.9.2 rebuilt and ran the image on Linux amd64. The final image size
is 1,620,527,848 bytes (1.62 GB decimal). The container ran as non-root UID
10001 with port 8001 bound only to Windows loopback. A named local model cache
volume held about 52 MB after the first analysis.

| Docker Desktop check | Observed result |
| --- | --- |
| API-only startup, cached volume | `/api/health` returned in 1.53 s from `docker run`; models load on first analysis, not at health time. |
| First two-model request | 38.47 s wall time for the checked-in bird JPEG, including initial external weight downloads. The result was HTTP 200. |
| Restart with cache | Both models returned the same scores and decisions in 3.26 s wall time on the first request after restart. |
| Fixed parity set | `scripts/verify_container.py` checked all eight gallery display JPEG hashes and 16 model results against `docs/GALLERY_MANIFEST.json`: revisions and decisions matched; maximum AI-score drift was 0.00000125. Total HTTP wall time was 2.304 s across eight warm comparisons. This is parity, not an accuracy estimate. |
| Memory after cached restart and parity | Container cgroup `memory.peak` was 569,716,736 bytes (543 MiB). This is a local WSL 2 sample, not a target-host capacity limit. |
| Invalid uploads | Corrupt image returned HTTP 400; 10 MB plus one byte returned HTTP 413. |

The repeatable parity check uses the app's already documented gallery display
files and does not change model thresholds or claim new detection accuracy.
The application loaders verify the packaged E2 NPZ, pinned MobileNet weights,
and pinned Community Forensics ONNX hash when they load. The Docker image and
`ios-model-cache` volume remain; the temporary test container was stopped and
removed. Reproduce the local trial from the repository root in a PowerShell
session with Docker Desktop running:

```powershell
docker build -t image-origin-api:local .
docker run -d --name image-origin-api -p 127.0.0.1:8001:8001 --mount type=volume,source=ios-model-cache,target=/home/ios/.cache image-origin-api:local
\.venv\Scripts\python.exe scripts\verify_container.py
docker image inspect image-origin-api:local --format '{{.Size}}'
docker stats image-origin-api --no-stream
docker restart image-origin-api
docker stop image-origin-api
docker rm image-origin-api
```

As a preliminary smaller-host check, the same image ran with
`--cpus=2 --memory=2g`. All eight parity files passed. The first request after process
start took 3.393 s including cached model load; the seven following warm
comparisons took 0.310–0.379 s each. A separate two-request HTTP sample (one
real and one generated display JPEG) completed in 0.99 s wall time, with
individual times of 0.988 s and 0.727 s. Container cgroup peak memory after
those requests was 573,108,224 bytes (547 MiB), below the 2-GiB local limit.
This is a single local workload with no sustained load, HTTP ingress, or AWS
CPU-equivalence claim. Reproduce the constraint with
`docker run --cpus=2 --memory=2g` and the same mount and port arguments above.

The first analysis on a new volume downloads the two pinned external weight
files. The volume is a local cache, not an image or result store. The `/api/health`
check intentionally reports API process health only; a hosted model-readiness
check or prewarm step remains a deployment decision. Local WSL 2 memory and
latency do not establish behavior on a smaller AWS CPU instance or under
sustained concurrent traffic.

## Next gate

The History browser checks are complete, and the owner reports completing the
C2PA edge check. The recorded synthetic suggestion verified the conflict UI;
a reproducible actual pinned-model conflict fixture was not retained in this
record. The local constrained-container
load run is complete, while uncached model download timing and AWS-target
hardware remain unmeasured. No connected AWS account was inspected for this
checkpoint. The owner subsequently chose an India region,
reported USD 100 credits remaining, and described a 7–14 day trial. The
[Mumbai trial proposal](AWS_TRIAL_PROPOSAL_2026-10-26.md) uses those inputs
and a provisional cost worksheet. Account eligibility and current
region-specific prices still need verification.
The proposed services, budget, privacy behavior, and teardown need owner review
before any paid AWS resource is created. Hosted
identity, private object storage, durable History metadata, and deployment
remain unimplemented.
