# Architecture and data flow

This guide describes the code in this repository and the owner-run public deployment confirmed on **29 October 2026**. Read the [project README](../README.md) for a product tour and local startup, or [Deployment and operations](DEPLOYMENT.md) for the host and remaining live checks.

## At a glance

| Layer | Responsibility | Code or configuration |
| --- | --- | --- |
| Browser | React interface, batch queue, gallery, result comparison, report generation, browser-side C2PA check, Cognito authorization-code flow with PKCE | `frontend/src/`, `frontend/public/` |
| HTTPS edge | Nginx serves the static build, routes `/api` to loopback, limits request size and rate | `infra/nginx-https.conf.template` |
| API | FastAPI validates image bytes, runs requested detectors, returns per-model results, and serves authenticated History routes | `backend/app/main.py`, `validation.py` |
| Models | Separate V3 E2 and Community Forensics pipelines, revisions, preprocessing, and cutoffs | `backend/app/v3_e2.py`, `model.py`, `backend/artifacts/` |
| Identity | Hosted Cognito JWT validation or loopback-only disposable test identities | `backend/app/auth.py`, `frontend/src/cognitoAuth.ts` |
| History | Local SQLite/files by default; private S3 originals and DynamoDB records in explicit AWS mode | `backend/app/history.py`, `cloud_history.py` |

The public deployment places Nginx and one Dockerized API process on an Ubuntu EC2 host in Mumbai (`ap-south-1`). Nginx terminates HTTPS and proxies to `127.0.0.1:8001`; port 8001 is not an intended public ingress. The browser uses the same origin for `/api` requests. The instance role grants the API the required S3 and DynamoDB operations, avoiding static AWS access keys in the container. The application does not use a queue or separate model worker.

## Analysis request

1. The user chooses one or both models and adds up to **eight** JPEG, PNG, or WebP images, each up to **10 MB**. The frontend analyzes files sequentially and can retry an individual failure.
2. For each file, the browser posts multipart data to `POST /api/analyze/compare`. The API validates the actual bytes, image format, dimensions, and corruption before inference. Selecting no model or an unknown model is rejected.
3. FastAPI loads each requested pinned model as needed and runs its own preprocessing and inference in a thread pool. V3 E2 combines FFT and frozen MobileNetV3-Small features with the packaged fusion head. Community Forensics runs its pinned ONNX model. A failure in one path becomes a per-model error while the other path can still succeed.
4. The response includes input metadata, a SHA-256 hash of the original bytes, analysis time, each model's revision/recipe/cutoff, scores or error, and elapsed time. The UI displays the results **separately**. It does not average their scores or decide which model is right.
5. `POST /api/inspect` is invoked only when the user opens the input inspector. It returns display views before tensor normalization. They show what each pipeline was fed, not which pixels caused a prediction.

The older `POST /api/analyze` endpoint remains for the original Community Forensics-only flow; the current UI uses `/api/analyze/compare`. `GET /api/health` checks that the API is serving but does not prove that model weights have loaded or that inference succeeds.

## Interpreting the models

V3 E2 uses a **0.50 AI-score cutoff**. Community Forensics uses its published **0.65 cutoff**. The displayed “real” score is `1 - AI score` within each pipeline. A score can therefore look AI-leaning while the suggestion remains “Real” below that model's threshold. Scores from the two pipelines are not interchangeable or generally calibrated probabilities of origin.

The owner trained the V3 E2 fusion head in a separate ML Project. This repository includes only its inference artifact and fitted scalers; it does not read training data or the sibling project at runtime. The frozen MobileNetV3-Small backbone and external ONNX baseline are downloaded at first use and hash-checked. The [artifact record](../backend/artifacts/README.md) lists the V3 E2 hashes. [Model review](evaluation/MODEL_REVIEW.md), [evaluation](evaluation/EVALUATION.md), and [dual-model evaluation](evaluation/DUAL_MODEL_EVALUATION.md) document results and claim boundaries.

## Content Credentials and reports

The frontend calls the C2PA browser SDK **on demand** against the uploaded original bytes. It shows whether a credential was found, whether it validated, signer/trust information where available, and possible conflicts with model suggestions. A signed credential is a statement bound to a file; it is a separate evidence source from the two detectors. The [C2PA record](C2PA_FEASIBILITY.md) details supported and unresolved states.

CSV export and per-image JSON/print-friendly reports are generated in the browser. A report includes the original byte hash, image metadata, model revisions/recipes, results or errors, and limitations; it does not contain the original image. Keep the original if exact reproduction matters. When an opted-in History item is reopened, the saved original and result snapshot allow its report and credential check to be rebuilt.

## History and data lifecycle

History is **off for guests and off by default for signed-in users**. Choosing Save sends `save_to_history=true` with the analysis. The API requires an identity and at least one successful model result. A save failure is returned as “not saved” without discarding the analysis result.

Hosted sign-in uses Cognito's authorization-code flow with PKCE. The API validates a bearer token against the configured user pool and uses its stable subject identifier for ownership. In hosted mode, the exact original bytes are stored under a private S3 prefix; DynamoDB stores result snapshots, metadata, per-owner counters, and a shared byte counter. The app's limits are **10 items / 50 MiB per owner** and **500 MiB across saved originals**. Records expire after **30 days**. Reads check the authenticated owner and expiry; deleting or expiring an item makes it unavailable immediately, while object/record cleanup is retried by an hourly sweep. [Local History verification](archive/HISTORY_LOCAL_VERIFICATION_2026-10-25.md) covers the earlier SQLite/files implementation. The live deployment conversation confirms one hosted save, but does not record a completed two-account isolation or failure/retry test.

Ordinary analysis still sends image bytes to the API. The application does not add guest or unsaved results to History. This statement is about application History behavior, not a blanket claim that network, system, or edge logs contain no request metadata. Saved originals can include EXIF and other embedded metadata. Users should upload only files they are comfortable sending to the hosted service.

## Configuration

| Setting | Meaning |
| --- | --- |
| `IOS_HISTORY_BACKEND` | `local` by default; `aws` selects the S3/DynamoDB adapter. |
| `IOS_HISTORY_ROOT` | Root for local SQLite/files History. |
| `IOS_LOCAL_TEST_AUTH=1` | Enables disposable Alice/Bob test sign-in **only on loopback**. Keep unset on the host. |
| `IOS_AWS_REGION`, `IOS_S3_BUCKET`, `IOS_DYNAMODB_TABLE` | AWS region and History resources; the instance role provides credentials. |
| `IOS_COGNITO_REGION`, `IOS_COGNITO_USER_POOL_ID`, `IOS_COGNITO_CLIENT_ID`, `IOS_COGNITO_DOMAIN` | Hosted identity settings. Cognito and AWS History must be configured together; a partial configuration fails at startup. |
| `HF_HOME`, `IMAGE_DETECTOR_MODEL_CACHE` | Downloaded model-cache locations. They are ignored locally and excluded from Git. |

The complete manual host procedure and Nginx/IAM templates are in [AWS self-deployment runbook](AWS_SELF_DEPLOY_RUNBOOK.md) and `infra/`. Do not commit account-specific values or credentials.

## Verification

Run the README's test, lint, gallery-manifest, frontend-format, and build commands after code changes. API tests stub the detectors; they are useful for route, validation, auth, ownership, quota, and failure behavior but do **not** test real-model quality. `scripts/verify_container.py` and the [26 October readiness record](archive/AWS_READINESS_2026-10-26.md) cover real-model container parity on the curated display files, restart, invalid upload, and local resource measurements. The [deployment guide](DEPLOYMENT.md#remaining-release-and-operations-checks) separates what the owner confirmed on AWS from the checks still needing direct evidence.
