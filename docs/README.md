# Documentation

Start with the [project README](../README.md) to try Image Origin Studio or run it locally. These pages cover the details that do not fit there:

- [Architecture](ARCHITECTURE.md) follows an image from upload through the two models and optional saved History.
- [Deployment and operations](DEPLOYMENT.md) records the AWS setup, how to update or stop it, and the live checks still outstanding. The [setup runbook](AWS_SELF_DEPLOY_RUNBOOK.md) has the manual EC2 steps.
- [Content Credentials](C2PA_FEASIBILITY.md) explains the browser check and what its results mean.

## Models and evaluation

The [project README](../README.md#how-v3-e2-was-developed) explains how the owner-trained V3 E2 model was built. The [evaluation log](evaluation/EVALUATION.md) records the external model selection and its observed mistakes. [Comparing the two detectors](evaluation/DUAL_MODEL_EVALUATION.md) explains why their historical percentages cannot be ranked against each other. The [paired pilot](evaluation/PUBLIC_PILOT_2026-10-24.md) shows how both behaved on the same twelve public images. The source lists, manifests, and per-image reports are kept beside those notes in [`evaluation/`](evaluation/).

## Gallery sources

The app reads [the gallery manifest](GALLERY_MANIFEST.json) directly. Its eight examples have separate [camera-photo](GALLERY_CAMERA_SOURCES.md) and [generated-image](GALLERY_PUBLIC_AI_SOURCES.md) source records. The gallery shows real product behavior, including model mistakes; it is not an accuracy sample. Licenses and third-party credits are in [Third-party notices](../THIRD_PARTY_NOTICES.md).

## Earlier work

The [project notes](archive/README.md) group earlier design plans, local checks, the AWS trial proposal, and the recent frontend redesign handoff. They are useful for understanding decisions, but [Deployment and operations](DEPLOYMENT.md) is the maintained source for hosting status. Local screenshots and example reports live under [`output/`](../output/).
