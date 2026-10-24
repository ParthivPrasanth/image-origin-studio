# Evaluation log

No model accuracy claim has been measured for this application yet. The author's published results are reported separately in the README.

## Implementation smoke check on 23 October 2026

The pinned model loaded and gave repeatable scores on three known-origin files. These were selected to check the inference path, including examples the earlier A3 detector missed in its viewed final set. They were **not** sampled for an accuracy estimate, and their outcomes must not be used to tune or choose a model. The files were read from the earlier project only for this local check; this repository has no runtime dependency on them. Their source identifiers and SHA-256 hashes are preserved in [the JSON report](sanity_smoke_2026-10-23.json).

| Source ID | Known origin | Prediction | Fake model score | Observation |
|---|---|---|---:|---|
| COCO val2017 `000000019402` | Real | Fake | 0.512428 | Wrong, close scores |
| SDXL `37740-short` | AI-generated | Fake | 0.560301 | Correct, close scores |
| SDXL `119641-long` | AI-generated | Real | 0.484775 | Wrong, close scores |

The first cold run took 48.343 seconds to fetch and load the model. A separate cached-process run took 8.365 seconds to start the model; its per-image CPU inference times were 0.179, 0.048, and 0.047 seconds. These are measurements from one PC, three files, and this particular run. They are not a cloud capacity estimate. The HTTP endpoint also returned the expected scores and pinned revision for `37740-short`.

## Future evaluation protocol

Before claiming any local accuracy, collect a modest set of independently sourced, known-origin images. Record every image's source, creation method or camera provenance, license, transformations, and whether it was used for any design decision. Include more than one generator if possible. Run the pinned model once with an agreed evaluation protocol, then report sample counts, confusion matrix, accuracy, and concrete failures. Do not remove gallery examples where the model is wrong.

| ID | Known origin | Source and license | Generator/camera | Transformations | Prediction | Fake score | Real score | Notes |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |
