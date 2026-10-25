# AWS readiness and first deployment implementation plan

**Status:** implementation plan for owner review, 25 October 2026. No AWS
resources have been created by this plan. Image Origin Studio currently runs
locally with two pinned models, browser-side Content Credentials checks, and
opt-in SQLite history for localhost test identities. The target is a small,
working AWS release that keeps guest analysis open and gives signed-in users
private, deletable history. [README](../README.md) describes the current app;
[local history verification](HISTORY_LOCAL_VERIFICATION_2026-10-25.md) records
what has been tested so far.

## Release target and boundaries

- A visitor can analyze an image without an account. Guest files do not enter
  account history. Any temporary processing copy has an explicit cleanup path.
- A signed-in user may opt in **before** analysis to save the exact original
  bytes and server result. History is scoped to the authenticated owner.
- Saved originals and results expire **30 days from saving**. Enforce **10
  saved images or 50 MiB per account**, whichever comes first, plus a **500 MiB
  shared saved-originals cap** for the first trial. The existing 10 MB upload
  limit remains. These are application limits, not a promise of free AWS use.
- The two models keep their current versions, separate preprocessing and
  thresholds. C2PA stays a separate claim about signed provenance, checked on
  original bytes. Do not add model retraining or a new accuracy claim to the
  deployment work.
- First release is a small portfolio/demo workload. No background queue,
  multi-region setup, autoscaling platform, or custom domain is required
  unless measurements, HTTPS/auth routing, or an explicit product need justify
  one. A queue is an option, not a milestone by itself.

## Sequence and decision gates

| Phase | Deliverable | Gate to continue |
| --- | --- | --- |
| 0. Local release sweep | Dated browser checklist and resolved blocking UI/privacy bugs | Guest and signed-in paths, result errors, deletion, and public gallery decision reviewed. |
| 1. Resource measurements | Repeatable script, CSV/JSON results, short sizing summary | Cold/warm time, peak RAM, CPU, and both-model load measured; no inference regressions. |
| 2. Linux container | Versioned Dockerfile, pinned artifacts, local run/stop guide | Real models start and return matching decisions after fresh start and restart. |
| 3. Costed AWS design | One chosen architecture, account/region/usage assumptions, price worksheet, IAM/data-flow diagram, teardown runbook | Owner reviews actual Billing/Free Tier state, numeric budget, costs, privacy, and exact resources **before provisioning**. |
| 4. Cloud adaptation | Hosted identity, private original store, production metadata store, quotas, cleanup, request controls | Guest and owner isolation tests pass locally against the selected interfaces. |
| 5. Trial deployment | Reproducible infrastructure and one complete cloud environment | Real browser end-to-end, deletion, failure, monitoring, costs, and teardown pass. |

Each phase can be committed and reviewed independently. Do not mark a phase
complete because code exists; keep its observations and failing checks in a
dated record under `docs/`.

### 0. Finish a short local release sweep

1. Check desktop and phone layouts for empty, loading, successful, partial
   model failure, eight-file batch, History, quota-full, deleted, and expired
   states. Check keyboard navigation and report save/print once. Record which
   Content Credentials cases were checked in the actual browser; the
   [C2PA record](C2PA_FEASIBILITY.md) names remaining case-specific gaps.
2. Resolve or explicitly defer any release-blocking issue. The gallery is a
   source-documented **local review draft**; obtain the owner's decision on
   its exact assets, labels, and reveal wording before including it in a
   public frontend build. If deferred, remove the gallery route and assets
   from the public build rather than publishing an unapproved draft.
3. Run backend tests/Ruff and frontend format/build checks; record versions,
   commit, and pass/fail results. Avoid a new model accuracy evaluation here.

**Likely files:** `docs/SITE_REDESIGN_REVIEW.md`, `docs/C2PA_FEASIBILITY.md`,
small frontend fixes only if observed, and a dated release-sweep record.

**Stop condition:** a privacy leak, broken history ownership, incorrect model
mapping, or a reproducible analysis failure blocks public deployment.

### 1. Measure the actual two-model workload

Add a repeatable script under `scripts/` that uses the app's real inference
path and fixed public/known-origin files without modifying the ML Project.
Record operating system, CPU, RAM, Python/package versions, model artifact
hashes, image sizes/formats, and whether weights were already cached. Save
raw measurements and the command used to reproduce them.

Measure at least:

- Fresh process with **V3 E2 only**, **Community Forensics only**, and **both**:
  model download separately from cached startup/load, peak resident memory,
  startup time, and CPU use.
- Warm one-image latency and a small batch for each mode; report median,
  slowest observed run, and the sample count. Include at least a small JPEG,
  large valid JPEG, PNG, and WebP. Measure the inspector separately because
  it sends the original again.
- Two concurrent requests and the current eight-file browser batch. Observe
  whether simultaneous inference doubles memory or blocks the API; set a
  safe initial concurrency limit from the result.
- Local history save/retrieve/delete latency and disk growth for exact
  originals. Estimate storage from realistic users and the fixed caps.

This is a **capacity** measurement, not detector accuracy. Use the results to
choose a CPU/memory class, model-loading strategy, request timeout, and
whether synchronous `/api/analyze/compare` is adequate. Do not promise a
specific AWS instance or Free Tier fit until this record exists.

**Gate:** both pinned models complete real inference within the chosen local
memory and timeout limits; the measurement script and data can be rerun.

### 2. Build and verify one Linux container

Create a CPU-only Dockerfile for the FastAPI service, pin the dependency set,
and keep model caches and user originals out of the image. Confirm the
packaged E2 NPZ and external ONNX/backbone hashes against their documented
revisions. Decide whether to prefetch weights into the image or a controlled
startup cache based on image size and cold-start measurements; document the
choice. Run as a non-root user, expose only the API port behind the eventual
HTTPS entry point, and provide a health check that does not falsely claim
models are loaded. Add a separate readiness check if the host needs one.

Test fresh build, first start, cached restart, both models, corrupt/oversized
image rejection, and a fixed real-file parity set. A Windows-only success is
not enough: the target is Linux behavior. Record image size, peak RAM,
startup time, warm latency, and exact run/stop commands. Use a local private
history directory only for development; the cloud release must not depend on
the container filesystem for retained originals or metadata.

**Likely files:** `backend/Dockerfile` or root `Dockerfile`, `.dockerignore`,
`scripts/measure_runtime.py`, container checks, and a dated sizing report.

**Stop condition:** the container cannot load both pinned models, decisions
drift from the saved local parity set, or its measured memory exceeds the
affordable host options; revise the architecture before spending.

### 3. Choose and price the smallest viable AWS design

Use Phase 1–2 measurements and a read-only check of the owner's AWS Billing
console. Record account plan, credit balance/expiry, Free Tier usage, intended
region, and whether each proposed service is available under that account.
AWS distinguishes Free and Paid account plans; paid-plan usage can incur
charges beyond credits, and a Free plan has its own expiry conditions. Treat
the account's Billing view as the source for eligibility, not a generic
“Free Tier” assumption. [AWS account-plan guide](https://docs.aws.amazon.com/us_en/awsaccountbilling/latest/aboutv2/free-tier-plans.html),
[usage tracking](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/tracking-free-tier-usage.html).

Design one primary path and one fallback:

| Component | Primary candidate to evaluate | Decision rule |
| --- | --- | --- |
| API/inference compute | One always-on CPU host/container with HTTPS routing | Fit measured both-model RAM, startup, latency, and monthly runtime cost. Avoid a queue if synchronous requests pass. |
| Frontend | Static build served from the same HTTPS origin or private S3 through CloudFront | Choose the lower-cost workable HTTPS/routing option; `/api` currently uses same-origin requests. |
| Hosted sign-in | Cognito managed login with authorization code + PKCE | Select only after pricing and an end-to-end token-validation design; guest Analyze stays open. |
| Saved originals | Private S3 bucket/object store | Block public access, owner-check downloads through API, no original in a public asset path. |
| History metadata | DynamoDB **or** another durable database that matches owner-list/get/delete/expiry access | Compare actual cost and operational work. SQLite in a single container filesystem is not a durable hosted history design. |
| Queue | None by default; SQS/worker only if measured request time or concurrency requires jobs | If added, specify retries, duplicate delivery, durable status, and delete-on-completion behavior. |
| Logs/alerts | Minimal operational logs and a cost budget | Keep image bytes, tokens, and private URLs out of logs; know how to stop the host and all resources. |

Draw the exact request/data flow and an itemized price worksheet for **24-hour
trial** and **one-month continuously running** scenarios. Include compute,
disk, public IPv4/networking, frontend/CDN, S3 storage/requests/downloads,
database reads/writes/storage/backups, hosted identity, logs, data transfer,
taxes if applicable, and any queue/load balancer. Show assumptions for users,
uploads/day, average original size, both-model share, request concurrency,
and 30-day retention. Note which costs scale with **guest inference**, because
image-count caps do not limit compute. Choose an owner-approved numeric
monthly budget and alert thresholds; a budget alert can arrive after costs
are incurred and is not a hard spending stop. [AWS Budgets guidance](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).

Write the resource inventory and exact teardown order **before** creating
anything: stop compute, disable ingress, remove test accounts and originals,
delete database/backup resources, CDN/DNS/logs/storage, then confirm Billing
and inventory. Keep secrets and account identifiers out of Git. The owner
reviews the chosen services, estimate, budget, trial duration, and teardown
as one concrete package. This is the **spending gate**.

### 4. Adapt authentication and private history for the chosen design

Keep the existing guest `/api/analyze/compare` contract and `save_to_history`
opt-in. Replace the localhost-only `IOS_LOCAL_TEST_AUTH` path for production;
it must be off and unavailable on the public host. Use hosted login with an
authorization-code/PKCE flow if Cognito is selected, and verify JWT signature,
issuer, audience/client, expiry, and token type on the API before deriving
`owner_sub`. Keep the browser's sign-out and refresh behavior explicit.
[Cognito managed login](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-managed-login.html)
supports a hosted sign-in page; [its token endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html)
documents PKCE. The final choice must be tested against the actual frontend
origin and redirect URLs.

Move exact originals to the selected private object store and result/owner
metadata to the chosen database. Keep one server-derived owner identity for
list, read, download, report, and delete. No client-supplied owner, object key,
hash, or model result is trusted. Apply per-user **10 items/50 MiB** and
shared **500 MiB** caps atomically across concurrent requests; if the chosen
database cannot enforce them as designed, change the data model before launch.
When a save fails, return the analysis result with a clear “not saved” state.
Keep a reconciliation path for object-written/record-failed cases.

At expiry or user deletion, deny reads immediately, delete original and
metadata through a retried application cleanup operation, and verify
completion. S3 lifecycle and DynamoDB TTL may be secondary safeguards, not
the only mechanism: S3 expiration is asynchronous and versioning changes what
delete means; DynamoDB TTL removal can lag by days. Decide whether S3
versioning/backups are disabled for originals, and document any backup
retention exception. [S3 expiration behavior](https://docs.aws.amazon.com/us_en/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html),
[DynamoDB TTL behavior](https://docs.aws.amazon.com/us_en/amazondynamodb/latest/developerguide/TTL.html).
Enable S3 Block Public Access for the original bucket; AWS recommends all
four settings for private buckets. [S3 access guidance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html).

Add bounded anonymous request rates, inference concurrency, file limits,
timeouts, and graceful overload responses. Test sign-in errors, expired
tokens, owner A/B isolation, opt-in off, exact-byte hash on retrieval,
partial-model failure, quota races, delete/retry, simulated 30-day expiry,
and restart recovery. Keep the gallery and case-report behavior intact.

**Likely files:** `backend/app/auth.py`, `backend/app/history.py`, a narrow
cloud storage/database adapter, `backend/app/main.py`, `frontend/src/App.tsx`,
`frontend/src/historyApi.ts`, configuration example without secrets, and
focused tests. Do not turn the local test identities into production users.

### 5. Deploy a short trial and prove it works

Use reproducible infrastructure code or scripted setup with all resource
names, region, configuration, and cleanup steps recorded. Prefer a single
small environment; avoid manually created extras that the teardown cannot
find. Grant the runtime only the permissions it needs for its own objects,
records, and logs. Keep the API behind HTTPS; ensure browser requests to
`/api` reach the right service without exposing local development ports.

Verify from a real browser and record dated evidence:

1. Guest Analyze works without login and creates no durable history item.
2. A signed-in user analyzes one image with saving off, then one with saving
   on. The saved original's SHA-256 matches the upload; report and on-demand
   C2PA checks use the right original.
3. Another account cannot list/read/download/delete that item. Logout blocks
   History. Invalid/expired tokens fail closed.
4. File-size, malformed image, quota-full, and partial-model-error paths show
   useful results without leaking originals or creating orphan records.
5. Delete one item and account data; verify immediate read denial and
   eventual object/record removal. Simulate expiry without waiting 30 days.
6. Capture real cold/warm latency, peak host RAM, logs, and observed trial
   charges/usage against the worksheet. Confirm budget alerts and a clear
   response if the estimate is exceeded.
7. Run the teardown in a disposable trial or prove it with a dry-run inventory
   and then remove all trial resources. Verify that no billable resources are
   left unintentionally.

Only after these checks should the README and resume call the site “deployed
on AWS.” Record the actual services, architecture, URL, commit, test result,
cost window, known limits, and operator/teardown instructions in `docs/`.

## Immediate next action

Start with Phase 0's short release sweep and Phase 1's measurement script.
They need no AWS provisioning and determine the affordable compute path.
After Phase 2, prepare the concrete Phase 3 cost/resource review; the owner
then has a specific deployment proposal to approve.
