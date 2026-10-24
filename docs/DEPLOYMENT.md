# Deployment guide for a first cloud project

## Current status

This repository currently runs on one PC. AWS is the planned deployment target, but no AWS resources have been created. The synopsis describes a possible AWS design and an older DINOv2/FFT model. This project uses the owner's V3 E2 model and the separately credited Community Forensics baseline described in the README.

## Terms

- **Frontend:** the React page shown in a browser.
- **API:** the FastAPI server receiving images and returning results.
- **Worker:** a separate process that would run slow model jobs from a queue.
- **Object storage:** private storage for uploaded files, such as S3.
- **Queue:** a service such as SQS that holds jobs until a worker can process them.
- **Database:** stores job status and results, not the model itself.

## Staged route

1. Run and test locally using the README commands. Try valid, corrupt, and oversized files.
2. Record download/load time, peak RAM, and warm inference time for V3 E2 alone, Community Forensics alone, and both loaded together. Repeat with several image sizes and a small batch. These measurements set the AWS compute requirement.
3. Choose AWS compute and supporting services that meet the measured requirements, then estimate cost using current pricing. Decide where images live and exactly when they are deleted. Plan authentication before retaining personal history.
4. Containerize the backend, add a persistent job queue and result store, and test retry/idempotency locally or in a sandbox.
5. Review the exact AWS services, region, monthly estimate, spending alert, and teardown commands before creating paid resources.
6. Deploy, verify private uploads and ownership, monitor failures, and document how to delete everything.

One possible AWS path is S3 → SQS → worker. The browser would ask the API for an upload URL and a job ID; the worker would take a queued job, run the model, and store a status/result that the browser can fetch. The exact services depend on sizing and cost review. This architecture is a design option, **not current functionality**.

## Release checklist

- Local inference validated on known-origin images with recorded sources
- Model and pretrained-backbone usage terms reviewed for the planned public deployment; [TorchVision notes](https://docs.pytorch.org/vision/master/models.html) that pretrained weights can have dataset-derived terms
- Memory/time measurements support host choice
- Image retention and account deletion rules written and tested
- File limits, request limits, private storage, and least-privilege access tested
- Failure/retry behavior and metrics verified
- Cost estimate, budget alert, and teardown reviewed
