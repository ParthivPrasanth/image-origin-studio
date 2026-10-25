# Local private-history verification — 25 October 2026

This is a local development check, not a hosted-account or AWS release.

## Verified

- Backend suite: `PYTHONPATH=backend; .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider backend\tests -q` passed **37 tests**. Pytest ran outside the managed sandbox because its Windows temporary fixture directory was inaccessible inside it.
- `python -m ruff check backend` passed. Frontend Prettier check and Vite production build passed; Vite needed permission to start its local esbuild helper in this managed environment.
- Local browser flow with stub detectors: Alice opted in before analysis of the public gallery `bird-display.jpg`; the app showed a saved status and expiry, then retrieved the stored original and separate result snapshot in History. After sign-out, Bob's History was empty. Alice's saved item remained visible after page refresh. Phone and desktop layouts were visually inspected; screenshots are `../output/review/history-phone.png` and `../output/review/history-desktop.png`.
- Store tests cover exact byte retrieval and SHA-256, sanitized filenames and opaque file keys, per-identity and shared atomic quotas under concurrent saves, ownership denial, pagination, expiry denial before cleanup, item/account deletion, failed-deletion retry, and orphan cleanup. API tests cover guest and signed-in unsaved paths, opt-in save, partial model failure, save-storage failure, a pending deletion response, invalid and expired tokens, and cross-identity reads/downloads/deletes.
- An offline real-model smoke request used the cached weights and one public gallery image. Both pinned models returned success through `/api/analyze/compare`: V3 E2 revision `v3-e2-e560a8a20a84` and Community Forensics revision `16db135220b318d811b207db576d90368980b595`. This checks integration, not accuracy.

## Limits and next gate

- The browser demonstration used stub scores; its displayed predictions are not model evidence. The offline real-model smoke only confirmed successful execution.
- Alice and Bob are localhost-only test identities. The bearer token is signed in the running process and expires after one hour; restarting the API invalidates it. There is no Cognito integration, production identity, cloud storage, or public access control.
- The local original directory uses the current Windows account's inherited access rules. The app does not encrypt originals itself. Hosted privacy, backups, deletion operations, request limits, capacity, cost, and exact AWS services require a separate owner review before deployment.
- The gallery still awaits owner approval of its exact cases, labels, and reveal wording before any public frontend release.
