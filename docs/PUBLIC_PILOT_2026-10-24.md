# Public paired pilot — 24 October 2026

## Purpose and source

This is a **small diagnostic run**, not a final accuracy benchmark or a claim
that either detector is generally better. It exercises the same API endpoint
used by the app on a frozen, known-label public sample. The images are not
committed here.

The 12 files are from [AI Detector Arena's public sample
repository](https://github.com/AI-Detect-Arena/benchmark-dataset) at commit
`3014b54eec9d44c7ef60b4c7e0cda6aeb4735d5b`. Its [dataset
card](https://github.com/AI-Detect-Arena/benchmark-dataset/blob/3014b54eec9d44c7ef60b4c7e0cda6aeb4735d5b/dataset_card.md)
says the six generated examples were made with Flux 2 Flex and the six real
examples are Unsplash photographs. There is one of each class in each broad
category: animal, art, food, landscape, portrait, and product. We relied on
the publisher's source labels; we did not independently verify every photo's
capture history. [Unsplash's license](https://unsplash.com/license) permits
use of its photos, subject to its stated restrictions. The dataset card states
research use for its generated images. We link the files and record hashes
without republishing them.

The exact file list, public source links, labels, and SHA-256 hashes are in
[`PUBLIC_PILOT_MANIFEST.csv`](PUBLIC_PILOT_MANIFEST.csv). The runner checks all
hashes and rejects duplicate bytes **before** loading either model. The
manifest hash in both reports is
`994bd2a6cd7c65296936b5fea4aa0dba68ab7ff1cf4ddb3d2a8203c961c9328d`.

## Fixed runs and observed results

Both models used their packaged revisions and published/fixed thresholds.
The `original` run sent each file's original bytes to both models. The
`jpeg90` run first applied the same declared JPEG quality 90, 4:4:4 encoding
to each file, then sent those bytes to both models. This second run checks one
format effect; it does not make the content sources identical.

| Variant | Model | Generated correctly flagged | Generated missed | Real falsely flagged | Real correctly kept | Errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Original | V3 E2 | 4/6 | 2/6 | 4/6 | 2/6 | 0 |
| Original | Community Forensics | 6/6 | 0/6 | 0/6 | 6/6 | 0 |
| JPEG 90 | V3 E2 | 4/6 | 2/6 | 4/6 | 2/6 | 0 |
| JPEG 90 | Community Forensics | 6/6 | 0/6 | 0/6 | 6/6 | 0 |

The V3 E2 misses were generated art and landscape; its real-image false
alarms were animal, food, landscape, and product. The JPEG variant did not
change any of the 24 model decisions, although scores shifted slightly.
See the complete per-image scores, predictions, model revisions, errors, and
timings in [`original JSON`](public_pilot_original_2026-10-24.json) and
[`JPEG JSON`](public_pilot_jpeg90_2026-10-24.json). Those files contain public
relative paths and source links, not the user's private images.

The sample is especially narrow: all six AI images come from **one
generator**, the real images are professional photos from **one source**, and
there is only one image per class and category. The public images predate the
Community Forensics release, so training or selection overlap cannot be
ruled out. Original AI files are PNG and real files are JPEG; the JPEG run
addresses that single format distinction, but many other source cues remain.
These results are useful for finding visible mistakes, not for ranking the
models on arbitrary uploads or for retuning E2's locked threshold.

## Reproduce without downloading the full archive

The repository's 36 public sample files total about 17 MB. The full archive
is about 1.5 GB and is unnecessary for this pilot. From the project root:

```powershell
git clone https://github.com/AI-Detect-Arena/benchmark-dataset.git .local\arena-benchmark
git -C .local\arena-benchmark checkout 3014b54eec9d44c7ef60b4c7e0cda6aeb4735d5b
$env:HF_HOME = (Join-Path (Get-Location) "model-cache")
.\.venv\Scripts\python.exe scripts\compare_models.py `
  --manifest docs\PUBLIC_PILOT_MANIFEST.csv `
  --image-root .local\arena-benchmark\samples `
  --output .local\pilot-original-new.json
.\.venv\Scripts\python.exe scripts\compare_models.py `
  --manifest docs\PUBLIC_PILOT_MANIFEST.csv `
  --image-root .local\arena-benchmark\samples `
  --variant jpeg90 --output .local\pilot-jpeg90-new.json
```

The runner refuses to overwrite an output file. Its confusion counts exclude
failed requests from accuracy calculations and report those failures
separately. A larger independent set with more photo sources, generators,
matched formats, and checked training overlap is the next evaluation gate;
see [`DUAL_MODEL_EVALUATION.md`](DUAL_MODEL_EVALUATION.md).
