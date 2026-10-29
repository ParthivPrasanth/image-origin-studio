# Documentation guide

Image Origin Studio is a public, single-host AWS deployment of a React/FastAPI image-screening app. This directory contains both **current guides** and **dated project records**. Start with the current guides; a dated record describes what was known at its stated checkpoint and may predate the live deployment.

## Start here

| If you want to… | Read |
| --- | --- |
| Understand the product, try it, or run it locally | [Project README](../README.md) |
| Follow a request through the browser, API, models, and saved History | [Architecture and data flow](ARCHITECTURE.md) |
| Understand the actual AWS deployment and operate it | [Deployment and operations](DEPLOYMENT.md) |
| Reproduce the owner-run, manual EC2 setup | [AWS self-deployment runbook](AWS_SELF_DEPLOY_RUNBOOK.md) |
| Find legal and source credits | [Third-party notices](../THIRD_PARTY_NOTICES.md) |

**Deployment status, 29 October 2026:** the owner confirmed the HTTPS site, model analysis, hosted sign-in, and one History save at [the public IP address](https://35.154.237.144/). A second-account isolation check, a budget-alert check, and inspection of the installed certificate-renewal schedule are not recorded as completed. The live address and resource state can change; [Deployment and operations](DEPLOYMENT.md) is the maintained status page.

## Evaluation and source evidence

| Record | Scope |
| --- | --- |
| [Model review](MODEL_REVIEW.md) and [evaluation log](EVALUATION.md) | Selection of the external baseline, observed errors, and limits of its 60-image check. |
| [Dual-model evaluation](DUAL_MODEL_EVALUATION.md) | V3 E2 background, why percentages from different sets cannot rank models, and the protocol for a new comparison. |
| [12-image public pilot](PUBLIC_PILOT_2026-10-24.md) with [manifest](PUBLIC_PILOT_MANIFEST.csv) | A paired diagnostic on the same files, including mistakes and source limitations. |
| [C2PA feasibility](C2PA_FEASIBILITY.md) | Browser credential behavior and the difference between signed claims, trust, and model suggestions. |
| [Gallery manifest](GALLERY_MANIFEST.json), [generated-image sources](GALLERY_PUBLIC_AI_SOURCES.md), [camera-photo sources](GALLERY_CAMERA_SOURCES.md) | Per-case sources, rights, transformations, hashes, and pinned display-image runs. Gallery selection is not an accuracy sample. |

## Implementation and verification records

| Record | What it captures |
| --- | --- |
| [Local History design](PRIVATE_HISTORY_IMPLEMENTATION_PLAN.md) and [verification](HISTORY_LOCAL_VERIFICATION_2026-10-25.md) | Local SQLite/files, test identities, ownership, quotas, expiry, deletion, and browser checks before AWS. |
| [AWS readiness, 26 October](AWS_READINESS_2026-10-26.md) | Local CPU/container measurements and parity checks. Its “no AWS resources” statement is true **at that checkpoint**, not the current status. |
| [Mumbai trial proposal, 26 October](AWS_TRIAL_PROPOSAL_2026-10-26.md) | Predeployment architecture and cost assumptions. The owner later chose a USD 20 planning ceiling and deployed the app; use the maintained deployment guide for current status. |
| [AWS implementation plan](AWS_IMPLEMENTATION_PLAN.md) and [milestone plan](NEXT_IMPLEMENTATION_PLAN.md) | Design decisions and build chronology. Their earlier future-tense cloud stages have since been completed in part by the owner-run deployment. |
| [Release check plan](RELEASE_CHECK_PLAN.md) | Local release checks; hosted checks are tracked in the deployment guide. |
| [Screen plan](WIREFRAMES.md), [redesign review](SITE_REDESIGN_REVIEW.md), and [implementation plan](SITE_REDESIGN_IMPLEMENTATION_PLAN.md) | Product design history. |
| [Product opportunities](PRODUCT_OPPORTUNITIES.md) | Researched ideas; they are proposals, not shipped features. |

The `output/` directory at the repository root contains historical local review captures and example report artifacts. Those images are not a live deployment screenshot and some show earlier wording. New contributors should use the app and current guides to learn the present behavior.
