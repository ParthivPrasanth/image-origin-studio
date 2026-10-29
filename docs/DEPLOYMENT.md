# Deployment and operations

**Maintained status · 29 October 2026.** Image Origin Studio is publicly reachable at [https://35.154.237.144/](https://35.154.237.144/). The owner-run deployment conversation records an HTTPS 200 from Nginx, a healthy `/api/health` response, successful use of both models, Cognito sign-in, and an image saved to History. A fresh API health request from the documentation update also returned HTTP 200. This is evidence of a working deployment at those times, not a guarantee of continuing uptime or full security verification. The endpoint is an Elastic IP; no custom domain is evidenced.

For first-time setup, the [self-deployment runbook](AWS_SELF_DEPLOY_RUNBOOK.md) provides console and shell steps. Its original predeployment wording and prices are dated; use this page for current status and the live AWS console for current costs. [Architecture and data flow](ARCHITECTURE.md) explains the code path.

## What is deployed

| Component | Purpose | Current arrangement |
| --- | --- | --- |
| Ubuntu EC2 host in Mumbai (`ap-south-1`) | Runs the public site and API | One host; this is a small, owner-managed deployment. |
| Nginx and HTTPS | Serves the React build and sends `/api` requests to FastAPI | Static files under `/var/www/image-origin-studio/`; API target bound to `127.0.0.1:8001`. HTTP redirects to HTTPS. |
| Dockerized FastAPI | Validates images, runs the pinned models, handles History | One `image-origin-api` container. First inference may download model weights. `/api/health` is a process check, not a model-readiness check. |
| Amazon Cognito | Hosted user identity | Authorization-code flow with PKCE in the browser; API validates access tokens. |
| Private S3 + DynamoDB | Opted-in History | S3 stores exact originals; DynamoDB stores result snapshots, metadata, and quota counters. Guest and unsaved analyses are not added to History. |
| EC2 instance role | AWS access for the API | Scoped to the configured History resources; no static AWS keys need to be placed in the container. |

The deployment uses **no load balancer, NAT gateway, queue, or separate model worker** in the documented topology. It runs analyses synchronously and the UI processes a batch sequentially. The [Nginx template](../infra/nginx-https.conf.template), [IAM template](../infra/iam-policy.json.template), and [Dockerfile](../Dockerfile) are parameterized source artifacts; actual resource identifiers and credentials must remain outside Git.

## Request and data path

1. A browser loads the React build over HTTPS from Nginx. Nginx forwards `/api` to the Docker container on loopback.
2. For analysis, the API validates the uploaded bytes and runs V3 E2 and/or Community Forensics. The response carries separate results. A guest can use this path without signing in.
3. For History, the browser signs in through Cognito. A signed-in user must select Save before the analysis; the API validates the token, saves the unmodified original to private S3, and records the result in DynamoDB. The code enforces 30-day expiry, 10 items/50 MiB per identity, and 500 MiB of saved originals globally.
4. History reads and deletes use the Cognito subject for ownership. Expired or deleting items are denied on read; an hourly background sweep retries cleanup. The live conversation establishes one successful save, while the full ownership/failure matrix below still needs a recorded host test.

The browser-side C2PA check uses original file bytes and stays separate from model inference. Reports are generated in the browser. Model scores are not proof of image origin or a substitute for a source record.

## Build and deploy a repository revision

The repository provides an owner-run PowerShell packager. On a Windows development machine with Docker Desktop, Python/npm dependencies, and the intended source revision checked out:

```powershell
.\scripts\package_aws_trial.ps1 -OutputDirectory .local/aws-trial-bundle-N
```

The output path must be new. The ignored bundle contains the frontend `dist/`, a Docker image archive, and a manifest with its SHA-256 and source-tree state. Review `working_tree_dirty` and the exact commit/diff before distributing a new build. Follow [runbook sections 3–4](AWS_SELF_DEPLOY_RUNBOOK.md#3-build-on-your-pc-and-transfer) to transfer, verify, and install the bundle on the EC2 host. The application copy in this repository is **not automatically deployed** when files change locally or when a GitHub repository is later created.

Before replacing a running container, record its current image ID and configuration privately so it can be restored if the new build fails. Replace the static build and container during a planned change window; then run the checks below. The runbook has the exact Docker command shape and Nginx template. Keep `IOS_LOCAL_TEST_AUTH` unset on the host. Cognito and AWS History settings must be configured together; a partial configuration fails at API startup.

## Verify an update

Run the repository's backend tests, lint, gallery-manifest verification, frontend format check, and build locally first; the [README](../README.md#developer-checks) lists the commands. On the actual host, record the deployed source revision and check:

```bash
sudo nginx -t
sudo docker ps --filter name=image-origin-api
sudo docker logs --tail 100 image-origin-api
curl --fail http://127.0.0.1:8001/api/health
```

From a browser or separate client, open the HTTPS root and check the certificate, then run **real inference** with known, non-sensitive images through each model. Check at least one failed/invalid upload, a guest analysis, sign-in, explicit save, reopening original bytes, and deletion. A healthy endpoint alone does not load the models or test S3, DynamoDB, Cognito, or the browser.

## Ongoing operation

- **Availability and performance:** inspect Nginx and container status, application errors, EC2 CPU credits, memory, disk, and request latency. This one-host topology has no automatic failover. Cold model loading and two concurrent requests should be measured on the actual host before making throughput claims.
- **Model cache:** a new host or container with an empty cache must download the pinned, hash-checked weights on first use. Confirm outbound access and perform a real inference before publicizing a new host.
- **TLS:** the runbook describes a short-lived Let's Encrypt IP certificate. The deployment chat records a successful `certbot renew --dry-run` and active cron service; it does **not** show the installed six-hour renewal job. Inspect `/etc/cron.d/` or the chosen scheduler, run a renewal dry run, and record certificate expiry and the Nginx reload hook. Missing renewal can make the site inaccessible within days.
- **Storage and retention:** review S3 object count/age and DynamoDB records, especially items pending deletion. The code's 30-day read expiry and hourly sweep should be checked against live resources. S3 lifecycle is a backup, not a substitute for application cleanup.
- **Cost:** the owner selected a **USD 20 maximum planning ceiling** after the original USD 35 proposal. The actual AWS Budget, alert thresholds, spend, credit use, and teardown date are not confirmed in the available deployment record. Check live Billing before further operation and set/verify alerts within that ceiling. A budget alert is **not a hard cap** and can lag. The earlier proposal's USD 35 figures are historical and must not be treated as current authorization to spend.
- **Backups:** the original trial design did not include a recoverable backup strategy. Do not describe saved History as durable against host, bucket, table, or account loss until backup and restore have been designed and tested.

## Remaining release and operations checks

These are **unverified in the available deployment record**, not claims that the implementation is broken:

| Check | Evidence to record |
| --- | --- |
| Account isolation | With two real Cognito accounts, verify account B cannot list, fetch, download, or delete account A's History item. |
| Retention and failure recovery | Verify 30-day denial, S3/DynamoDB cleanup, one deliberate deletion failure followed by retry, and account-wide deletion. |
| Quotas and request controls | Exercise owner/global History limits and check Nginx upload/rate limits on the host. |
| TLS renewal | Show the installed schedule, dry-run result, deploy hook, and current certificate expiry. |
| Cost controls | Record the live budget/alerts, actual pre-credit and out-of-pocket spend, service pricing, and teardown date under the USD 20 planning ceiling. |
| Capacity | Record cold start, memory, CPU credits, request timing, and at least two concurrent requests on the EC2 host. |
| Deploy reproducibility | Record the source revision, manifest SHA-256, image ID, configuration, and post-deploy smoke result for each public update. |

Do not use private user images for these checks without their permission. Use disposable accounts and known, non-sensitive fixtures.

## Stop and teardown

To stop public use promptly, close ingress at the security group or Nginx, then stop the API container. Disabling the service does not itself remove charges. At the agreed trial end, delete saved test History through the app, verify S3 and DynamoDB cleanup, and then remove the trial bucket, table, Cognito resources, EC2 instance and disk, Elastic IP, IAM role/policy, security group, logs, and Budget. Check Billing after its reporting delay. The [runbook teardown inventory](AWS_SELF_DEPLOY_RUNBOOK.md#6-teardown-on-the-trial-end-date) lists the full manual sequence. Record actual costs and deletion evidence in a private operator note, not this public repository.
