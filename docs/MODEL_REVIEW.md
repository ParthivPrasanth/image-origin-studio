# Model review after local failures

This file records how Community Forensics became the app's external baseline. The later V3 E2 integration does not change this historical selection record. See [the dual-model comparison protocol](DUAL_MODEL_EVALUATION.md) for the rules governing any new head-to-head result.

## Why the current model is under review

On 24 October 2026, the pinned `jacoballessio/ai-image-detect-distilled` model was run on a user folder with 9 files labeled `ai` and 6 labeled `real`. The labels are provisional: the precise origin of every file is unknown. Two `ai` files were byte-for-byte duplicates. The model called 5 of the 6 `real` files AI-generated and called both copies of the same `ai` image real. Hugging Face's reference pipeline reproduced two representative scores, so these errors are not caused by the app's label mapping or image processor.

This is a diagnostic of this folder, not an accuracy estimate. The images and file-level report stay in ignored local files. The folder has already been viewed, so it will not be used to tune thresholds or select a replacement.

## Replacement candidate and comparison rule

`Thermostatic/community-forensics-frontier-detector-2026-08` at revision `16db135220b318d811b207db576d90368980b595` is a candidate because it is MIT-licensed, has published model and preprocessing details, offers a 44 MB FP16 ONNX artifact, and reports class-specific development results. Its published robustness report also records failed gates; its validation is development evidence, not an untouched test estimate. The published raw-logit decision boundary is **1.359375**; no threshold will be fitted to the user's images.

Before replacing the running model, compare it with the current model on one fixed, separate sample from `saberzl/So-Fake-OOD` revision `b4b34d16fda2020c2923a21d431d1ab3acbdbaff`: 30 real images and 30 fully synthetic images, excluding localized edits. The sample rule is ten 100-row pages at offsets 0, 10,000, ..., 90,000, then the first 30 of each label sorted by SHA-256 of `fixed-2026-10-24:` plus the row ID. Cache source IDs and image hashes before inference. Use each model's published preprocessing and fixed decision rule. Report confusion matrices by group and all failures. This small sample is a screening gate, not a general accuracy claim.

Promote the candidate to an **experimental** default only if real-photo specificity is at least 80%, synthetic recall is at least 70%, balanced accuracy exceeds the current model by at least 15 percentage points, neither class is more than 5 points worse than the current model, and its runtime and dependencies can be reproduced inside this repository. If any gate fails, keep the candidate separate and revisit the model choice. Do not keep searching thresholds against this test sample.

## Recorded outcome

The fixed sample had 60 distinct files. The original model's balanced accuracy was 50.0% (18/30 real specificity, 12/30 synthetic recall). The candidate's balanced accuracy was 85.0% (25/30 real specificity, 26/30 synthetic recall), passing every numerical gate. Its published ONNX artifact agreed with the PyTorch candidate on all 60 decisions, and the app's own ONNX path agreed with the standalone ONNX run. The model is now the experimental default. See [the full evaluation log](EVALUATION.md) and [row-level report](model_comparison_2026-10-24.json).

## Deployment interpretation

Even a model that passes this gate cannot establish image provenance. The next evaluation needs more sources and transformations, with verified origin and no overlap with training or selection data. Cloud sizing must use measured startup, peak RAM, and inference time for the selected model.
