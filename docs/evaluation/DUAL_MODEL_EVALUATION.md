# Comparing the two detectors

## What the comparison means

The application can show two independent suggestions for the same uploaded image:

- **V3 E2:** the owner's trained fusion head and training-fitted scalers on 64 FFT features and 848 features from a frozen, ImageNet-pretrained MobileNetV3-Small backbone. Its fixed AI decision threshold is 0.5.
- **Community Forensics:** a separately credited pretrained detector used as the external baseline. Its pinned model, preprocessing, and published AI flagging rule are recorded in `backend/app/model.py`.

Each detector processes the same uploaded file with its **own** required preprocessing. Their displayed scores have different training and calibration histories. A larger number from one detector does not mean it has stronger evidence than the other. Agreement or disagreement is useful to inspect, but neither establishes the image's origin. Do not average the scores or choose a winner from an unlabeled upload.

## Existing evidence and its limits

The V3 E2 model was selected and tested under a locked protocol in the separate ML Project. Its 92% clean and JPEG-50 balanced accuracy came from a 200-image COCOXGEN/COCO final group. The final group has been viewed, and source format, size, crop, and generator remain confounded. Saved out-of-source diagnostics on older Tiny-GenImage groups were weaker. These artifacts are historical evidence; they must not be retuned or represented as general upload accuracy.

The Community Forensics model replaced an earlier app model after a fixed 60-image So-Fake-OOD screening comparison. Its 85% balanced accuracy on that small sample is also historical selection evidence. The 92% and 85% figures are **not** a head-to-head comparison: they come from different images and protocols. The owner's `images test` folder has uncertain origins and a duplicate, so it is diagnostic only.

## Protocol before a new performance claim

1. Choose an independently sourced, known-origin collection **before** running either detector on it. Aim for multiple real-image sources and multiple generators, with matched content and source formats where feasible. Record license/permission, source ID, original format and size, camera or generator, edits, and hashes. Exclude known E2 training/development/final rows and previously viewed app selection images. Check possible Community Forensics training overlap against its published sources; document any uncertainty that cannot be resolved.
2. Freeze the image identities, two model versions and hashes, preprocessing, decision thresholds, subgroup definitions, and metrics in a dated manifest. Do not tune either model or threshold on these images. Run both models on the same original bytes, allowing each model its own fixed transform.
3. Save one row per image and model: source ID, origin label, image hash, model ID/version, score, prediction, elapsed time, and any failure. Preserve all failures and model disagreements. Do not commit private paths or images without permission.
4. Report real and AI counts, each confusion matrix, balanced accuracy, AI recall/F1, real-image false-positive rate, and source/generator/format subgroups. Include paired correctness and disagreement examples. State sample-size and overlap limits beside every headline number.

The comparison can be shown in the app before this evaluation is complete. In that state it is a **side-by-side inspection tool**, not evidence that either detector is more accurate overall. Keep the existing V3 and Community Forensics evaluation files unchanged.

A [small public paired pilot](PUBLIC_PILOT_2026-10-24.md) ran both models on the same 12 files and exposed concrete V3 E2 misses and false alarms. It uses one generator and one real-photo source, with unknown Community Forensics training overlap, so it does **not** satisfy the larger independent evaluation gate above.

## Implementation parity gate

Before using copied E2 artifacts in this app, verify their hashes against the ML Project's V3 lock and reproduce original E2 scores and decisions on a small, fixed set of known image bytes. Check input orientation, center-square crop to 224 pixels, FFT ordering, MobileNet transform and feature ordering, both training-fitted scalers, the fusion head state, and threshold 0.5. This gate checks the port, not model quality.
