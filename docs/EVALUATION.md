# Evaluation log

The current model has a small, separate screening comparison below. Its result is not a general accuracy claim. The 23 October check is historical evidence for the original model and was not used to select this replacement.

## Historical implementation smoke check on 23 October 2026

The original `jacoballessio/ai-image-detect-distilled` model loaded and gave repeatable scores on three known-origin files. These were selected to check the inference path, including examples the earlier A3 detector missed in its viewed final set. They were **not** sampled for an accuracy estimate, and their outcomes must not be used to tune or choose a model. The files were read from the earlier project only for this local check; this repository has no runtime dependency on them. Their source identifiers and SHA-256 hashes are preserved in [the JSON report](sanity_smoke_2026-10-23.json).

| Source ID | Known origin | Prediction | Fake model score | Observation |
|---|---|---|---:|---|
| COCO val2017 `000000019402` | Real | Fake | 0.512428 | Wrong, close scores |
| SDXL `37740-short` | AI-generated | Fake | 0.560301 | Correct, close scores |
| SDXL `119641-long` | AI-generated | Real | 0.484775 | Wrong, close scores |

The first cold run took 48.343 seconds to fetch and load the model. A separate cached-process run took 8.365 seconds to start the model; its per-image CPU inference times were 0.179, 0.048, and 0.047 seconds. These are measurements from one PC, three files, and this particular run. They are not a cloud capacity estimate. The HTTP endpoint also returned the expected scores and pinned revision for `37740-short`.

## Separate 60-image screening check on 24 October 2026

Before running either model on this sample, the selection rule and promotion gates were recorded in [model review](MODEL_REVIEW.md). The sample contains 30 Reddit images labeled real and 30 fully synthetic images from 12 generator buckets in `saberzl/So-Fake-OOD`. It excludes locally edited images because both models classify whole images. All 60 downloaded files had distinct SHA-256 hashes. Dataset revision, sample rule, source IDs, hashes, predictions, and scores are in the [comparison report](model_comparison_2026-10-24.json). No source images are committed.

| Model | Real called real | Real called AI | Generated called AI | Generated called real | Balanced accuracy |
|---|---:|---:|---:|---:|---:|
| Original distilled model | 18/30 | 12/30 | 12/30 | 18/30 | 50.0% |
| Frontier candidate, published boundary | 25/30 | 5/30 | 26/30 | 4/30 | 85.0% |

The candidate passed the recorded 80% real-specificity, 70% generated-recall, and 15-point improvement gates. It still made **9 errors**. The ONNX deployment artifact and its PyTorch weights made the same 60 decisions; their mean absolute raw-logit difference was 0.0076, with a maximum of 0.0409. The app's ONNX inference path also reproduced all 60 ONNX decisions. Cached model startup took 0.868 seconds in one run; median warm per-image CPU inference was 0.418 seconds (59 images). These timings are from one PC, not hosting estimates.

The sample is small and deliberately balanced, contains only one real-photo source, and may not cover a user's generator, camera, edits, or compression. Its labels are supplied by the dataset and were not independently audited. Training overlap has not been independently ruled out. The user's previously viewed and partly uncertain folder was **not** used to set the candidate's threshold or the promotion gates. As a follow-up diagnostic only, the candidate called 5 of its 6 `real` files real and 7 of its 9 `ai` entries AI; the two missed `ai` entries are an identical duplicate, so that is one distinct missed image. One `real` file remained a false positive. These folder counts are provisional because exact provenance is unknown.

## Future evaluation protocol

Before claiming any local accuracy, collect a modest set of independently sourced, known-origin images. Record every image's source, creation method or camera provenance, license, transformations, and whether it was used for any design decision. Include more than one generator if possible. Run the pinned model once with an agreed evaluation protocol, then report sample counts, confusion matrix, accuracy, and concrete failures. Do not remove gallery examples where the model is wrong.

| ID | Known origin | Source and license | Generator/camera | Transformations | Prediction | Fake score | Real score | Notes |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |
