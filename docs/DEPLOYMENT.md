# Deployment guide for a first cloud project

## Current status

This repository currently runs on one PC. No AWS resources have been created. The synopsis describes a future AWS design, but it also describes an older DINOv2/FFT model. This project uses the credited ViT model named in the README.

## Terms

- **Frontend:** the React page shown in a browser.
- **API:** the FastAPI server receiving images and returning results.
- **Worker:** a separate process that would run slow model jobs from a queue.
- **Object storage:** private storage for uploaded files, such as S3.
- **Queue:** a service such as SQS that holds jobs until a worker can process them.
- **Database:** stores job status and results, not the model itself.

## Staged route

1. Run and test locally using the README commands. Try valid, corrupt, and oversized files.
2. Record model download/load time, peak RAM, and warm inference time. Repeat with several image sizes and a small batch. These measurements set the hosting requirement.
3. Choose a host and estimate cost using its current pricing. Decide where images live and exactly when they are deleted. Plan authentication before retaining personal history.
4. Containerize the backend, add a persistent job queue and result store, and test retry/idempotency locally or in a sandbox.
5. Review the exact provider, services, monthly estimate, spending alert, and teardown commands before creating paid resources.
6. Deploy, verify private uploads and ownership, monitor failures, and document how to delete everything.

For AWS, S3 → SQS → worker is one possible path. The browser would ask the API for an upload URL and a job ID; the worker would take a queued job, run the model, and store a status/result that the browser can fetch. This architecture is a design option, **not current functionality**.

## Release checklist

- Local inference validated on known-origin images with recorded sources
- Memory/time measurements support host choice
- Image retention and account deletion rules written and tested
- File limits, request limits, private storage, and least-privilege access tested
- Failure/retry behavior and metrics verified
- Cost estimate, budget alert, and teardown reviewed
