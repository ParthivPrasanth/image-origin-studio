# Optional local private analysis history

**Status:** local-development slice implemented and verified, 25 October 2026.
See [HISTORY_LOCAL_VERIFICATION_2026-10-25.md](HISTORY_LOCAL_VERIFICATION_2026-10-25.md)
for the backend, browser, and offline model checks and their limits.
This slice is for localhost development only. It uses disposable local test
identities behind `IOS_LOCAL_TEST_AUTH=1` (off by default), stores opted-in
history on the local machine, and creates no Cognito integration or AWS
resources. Hosted sign-in and cloud storage remain a separate later decision.
Analysis and the gallery must remain usable without signing in or saving.

## Intended experience

- **Guest:** upload and analyze as now, without signing in. The application
  creates no durable history record or retained original for history; guest
  results remain temporary in the browser and process.
- **Local test identity:** a clearly labeled local-only sign-in is exposed
  only when the API is started with `IOS_LOCAL_TEST_AUTH=1` and the request is
  from loopback. The switch is off by default. Alice and Bob are test fixtures,
  not real accounts or a production authentication system.
- **Opt-in save:** an authenticated local test user can turn on **Save this
  analysis to my history** before submitting. The control starts off. Only
  this choice stores the exact original bytes and server-produced result in
  private local development storage. A saved result shows its expiry date and
  a link to History. Analysis remains available when saving is off.
- **History:** requires the local test identity. It lists that identity's
  saved images and model results, newest first. Opening an item shows its
  original, stored result snapshot, report actions, expiry, and **Delete**.
  Every read and delete must enforce ownership. Content Credentials are checked
  on demand against the retrieved original; a browser-supplied C2PA status is
  not silently stored as verified server evidence.
- **Sign-in timing:** saving requires sign-in before analysis. A guest who
  decides to save later must sign in and analyze the file again. Do not
  quietly upload or retain guest files during a sign-in redirect.

The model suggestion, score, threshold, revision, and error fields stay
separate from provenance and from the user's account identity. Saving does
not turn model output into an origin verdict.

## Implemented local retention and deletion rules

| Item | Local rule |
| --- | --- |
| Unsaved guest upload | Used for analysis, then discarded; no history row or durable original. Cloud job copies are outside this local slice. |
| Saved original and analysis | Retain for **30 days from saving**; viewing does not extend expiry. Show the expiry date in History. |
| Per-identity limit | **10 saved images or 50 MB**, whichever comes first, under the existing 10 MB per-file limit. Show remaining space; reject a save cleanly when full while still returning the analysis result. |
| Shared local limit | **500 MB of saved originals across the local installation**. Stop new saves when reached while leaving unsaved analysis available. This is a local guardrail, not a cloud cost or capacity estimate. |
| Delete one item | Make it unavailable immediately, remove its original and result, and report cleanup failures clearly. Verify that the item cannot be read after deletion. |
| Delete a test identity's data | Remove all saved originals and results for that identity before allowing its history to be considered cleared. Verify the outcome; this is test data cleanup, not production account deletion. |
| Backups | The local prototype makes no application backup copies. The owner controls any operating-system or manual backup of the project folder; those copies are outside application deletion guarantees. |

At the 30-day expiry, reads are denied even if physical cleanup is still
running. The API runs a cleanup sweep at startup and every hour while it is
running. It marks expired rows for deletion, retries pending deletions, and
removes orphaned originals. If the API is stopped at expiry, physical cleanup
waits until it starts again. AWS lifecycle and database expiry behavior need
a separate design for hosted history.

Cloud references for a later hosted-history review (outside this local slice):
[S3 lifecycle deletion](https://docs.aws.amazon.com/us_en/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html),
[DynamoDB TTL timing](https://docs.aws.amazon.com/us_en/amazondynamodb/latest/developerguide/TTL.html),
[DynamoDB recovery windows](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Point-in-time-recovery.html).

## Data and access design

For local development, keep the SQLite database and exact original bytes
under the ignored project `.local/` directory, outside the public gallery.
The application must not serve this directory as static content. A history
record contains `history_id`, server-derived `owner_sub`, opaque generated
file reference, sanitized display filename, MIME type, byte count, original
SHA-256, creation/expiry timestamps, deletion state, selected models, and the
exact server result snapshot (including partial-model errors and model/recipe
revisions). Do not trust a client-sent user ID, result, hash, or file path.
Enforce the per-identity quota atomically and enforce the shared local cap.

Every list, read, original download, report, and delete operation checks the
local test identity against `owner_sub`. Return the same unavailable response
for another identity's ID and an unknown ID. Private-image responses use
`Cache-Control: no-store`; the browser clears local previews and history state
on sign-out. Do not log image bytes or tokens. The application does not encrypt
local files itself; anyone with access to the same Windows account or project
files may be able to inspect them. Original files may contain location and
other EXIF data, so the save control must say that the unmodified file is kept.

## Implemented local sequence and later work

### 1. Fix the save contract and local storage layout

- Extend the existing `POST /api/analyze/compare` request with an explicit
  `save_to_history` flag. With the flag off, retain the current guest path.
  With it on, require an authenticated user. Run inference on the same
  validated bytes, then persist those exact original bytes and the
  server-created result snapshot. Return a `history_id`, expiry, and save
  status separately from the model result. A storage failure must leave the
  analysis visible and say that it was not saved.
- Add a small local database (SQLite under ignored `.local/`) and a private
  ignored file directory for development. Create a versioned schema or
  migration so records survive restarts. Keep storage operations behind a
  narrow module; choose the production database during AWS readiness from
  access patterns and cost rather than assuming a service now.
- Save only if at least one selected model succeeded. Preserve any other
  model error in the saved snapshot. If file storage succeeds but the record
  write fails, remove the orphaned file; a reconciliation job catches any
  remaining orphans.

**Implemented in:** `backend/app/main.py`, `backend/app/history.py` (SQLite
schema and private file operations), and focused tests under `backend/tests/`.

### 2. Add identity checks without forcing login for analysis

- Add optional bearer-token processing for ordinary analysis and require
  verified local identity for `save_to_history` and `/api/history/*`. Derive
  the owner from the verified token subject, never from a client-sent ID.
- Use clearly labeled disposable test identities for localhost only. Require
  `IOS_LOCAL_TEST_AUTH=1`, keep it off by default, and fail closed for non-loopback
  requests. Do not add passwords or imply this mechanism is suitable for a
  public or multi-user service. No Cognito integration or AWS resource is part
  of this local implementation.
- Keep the public guest analysis path available without sign-in. Add request
  rate and concurrency controls before any public exposure because anonymous
  inference consumes model compute.

**Implemented in:** `backend/app/auth.py`, `frontend/src/api.ts`, the frontend
account/session UI, and auth/ownership tests.

### 3. Build the History API and screen

- Add `GET /api/history` (paginated), `GET /api/history/{id}`,
  `GET /api/history/{id}/original`, `DELETE /api/history/{id}`, and an
  account-data deletion operation. All operations use server-derived owner
  identity. Do not expose arbitrary storage keys or filesystem paths.
- Add a **History** destination that asks guests to sign in while Analyze and
  Gallery remain open. Show saved/unsaved state, expiry, quota, pending
  deletion, and errors. A record opened from history uses the same result
  presentation and report tools as a fresh analysis.
- Keep the JSON report's byte hash, model revisions, and score fields. When
  Content Credentials are checked in History, validate the downloaded
  original in the browser again rather than labeling a cached browser claim
  as a server verification.

**Implemented in:** `backend/app/main.py`, `frontend/src/App.tsx`,
`frontend/src/History.tsx`, and `frontend/src/historyApi.ts`.

### 4. Make deletion reliable

- Use `active → deleting → removed` states. Mark `deleting` first so reads
  stop, delete the original, then remove the database record. Retry failures
  and monitor items stuck in `deleting`; do not delete the last pointer to an
  object before confirming its removal.
- Run an expiry sweep and orphan-file reconciliation against local storage.
  Test deletion of all history for a local test identity.
- Document the user-visible retention policy and local cleanup behavior.
  Verify an expired or deleted ID cannot be accessed even while physical
  cleanup is pending.

### Later cloud work (outside this local slice)

- A hosted version needs a separately reviewed identity provider, private
  image store, database, compute sizing, request controls, expiry/deletion
  behavior, current price estimate, budget alert, and teardown plan. The local
  limits here do not establish cloud capacity or cost. Do not provision AWS
  resources as part of this local feature.
- Before an AWS proposal, measure model load, RAM, latency, container
  behavior, database operations, private image storage, expected image traffic,
  and realistic active-user counts. Check the actual account's current plan
  and billing details. The 10-item/50-MB identity limit and 500-MB local cap
  do not limit inference compute, requests, downloads, or cloud charges.

For a later hosted release, check the current [AWS Billing Free Tier guide](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/tracking-free-tier-usage.html)
and pricing before deciding on services.

## Verification and completion gate

The local verification record covers guest analysis
without any history write; signed-in unsaved analysis; saved analysis with
byte-for-byte original retrieval and matching SHA-256; partial-model error;
per-identity and shared quotas; storage failure; invalid/expired token;
cross-identity list/read/download/delete attempts; logout; page refresh;
single-item and test-identity data deletion; 30-day expiry; and failed cleanup
retry. The UI was reviewed at phone and desktop widths; backend tests, Ruff,
frontend format check and build, and an offline real-model smoke check passed.
See the linked verification record for exact scope and results.

The local slice is complete: guests can use Analyze unchanged, local test
identities can opt in and revisit exact originals and results, another
identity cannot access them, and deletion and expiry were tested. Public
release is a separate project requiring hosted sign-in,
private cloud storage, a production database choice, resource limits, cost
review, and end-to-end cloud checks.
