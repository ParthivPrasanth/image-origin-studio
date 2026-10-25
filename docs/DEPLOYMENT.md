# Deployment guide for a first cloud project

## Current status

This repository currently runs on one PC. AWS is the planned deployment target, but no AWS resources have been created. Optional private history is implemented and verified for localhost test identities; see the [local verification record](HISTORY_LOCAL_VERIFICATION_2026-10-25.md). The synopsis describes a possible AWS design and an older DINOv2/FFT model. This project uses the owner's V3 E2 model and the separately credited Community Forensics baseline described in the README.

For the local history slice, saving is opt-in and keeps the exact original
plus its analysis for 30 days. Implemented limits are 10 images or 50 MB per local
test identity and 500 MB combined saved originals across local identities.
Guests remain unsaved. Local test authentication is gated by
`IOS_LOCAL_TEST_AUTH=1` and is
off by default; it is not Cognito, production authentication, or an AWS
integration. The application does not encrypt local history files itself.
These local limits do not establish cloud capacity, cost, or security.

## Terms

- **Frontend:** the React page shown in a browser.
- **API:** the FastAPI server receiving images and returning results.
- **Worker:** a separate process that would run slow model jobs from a queue.
- **Object storage:** private storage for uploaded files, such as S3.
- **Queue:** a service such as SQS that holds jobs until a worker can process them.
- **Database:** stores job status and results, not the model itself.

## Staged route

The detailed, measurement-first work plan is
[AWS_IMPLEMENTATION_PLAN.md](AWS_IMPLEMENTATION_PLAN.md). Use its phase gates
and record the actual account/region costs before selecting services.

1. Run and test locally using the README commands. Try valid, corrupt, and oversized files; check the on-demand inspector and browser-generated case report too.
2. Review the verified [local private-history slice](PRIVATE_HISTORY_IMPLEMENTATION_PLAN.md): guests stay unsaved; saving is off until a signed-in local test user opts in. Keep `IOS_LOCAL_TEST_AUTH=1` unset except when reviewing that local flow.
3. Finish the remaining post-redesign live-state visual checks, then record download/load time, peak RAM, and warm inference time for V3 E2 alone, Community Forensics alone, and both loaded together. Repeat with several image sizes and a small batch. These measurements set the AWS compute requirement.
4. As a separate later stage, choose AWS compute and supporting services that meet the measured requirements, then estimate cost using current pricing. Review hosted sign-in, the history database, private originals, 30-day retention, and request controls. The local 10-image/50-MB and 500-MB caps are not AWS sizing or cost assumptions. Check the account's actual Free Tier plan and credit balance in Billing; no storage cap guarantees zero cost.
5. Containerize the backend and test startup, pinned weights, and restart locally. Add a queue only if the measurements justify it; then test retries and idempotency.
6. Review the exact AWS services, region, monthly estimate, spending alert, and teardown commands before creating paid resources.
7. Deploy, verify private uploads and ownership, monitor failures, and document how to delete everything.

One possible AWS path is S3 → SQS → worker. The browser would ask the API for an upload URL and a job ID; the worker would take a queued job, run the model, and store a status/result that the browser can fetch. The exact services depend on sizing and cost review. This architecture is a design option, **not current functionality**.

## Release checklist

- Local inference validated on known-origin images with recorded sources
- Local history guest path, explicit save opt-in, exact-original retrieval, identity ownership, 30-day expiry, and deletion verified before describing the flow as complete
- Model and pretrained-backbone usage terms reviewed for the planned public deployment; [TorchVision notes](https://docs.pytorch.org/vision/master/models.html) that pretrained weights can have dataset-derived terms
- Memory/time measurements support host choice
- Image retention and account deletion rules written and tested
- File limits, request limits, private storage, and least-privilege access tested
- Failure/retry behavior and metrics verified
- Cost estimate, budget alert, and teardown reviewed
