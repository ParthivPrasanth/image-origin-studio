"""Run a locked, paired diagnostic on a known-origin image manifest.

This script records evidence; it never fits a model or changes a threshold.
Run it once per frozen manifest and variant. Output files cannot be overwritten.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.main import app  # noqa: E402
from app.model import MODEL_ID as BASELINE_ID  # noqa: E402
from app.model import MODEL_REVISION as BASELINE_REVISION  # noqa: E402
from app.v3_e2 import ARTIFACT_SHA256, MOBILE_WEIGHT_SHA256  # noqa: E402
from app.v3_e2 import MODEL_ID as E2_ID  # noqa: E402
from app.v3_e2 import MODEL_REVISION as E2_REVISION  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

FIELDS = (
    "path", "sha256", "known_origin", "source_id", "category", "generator",
    "source_url", "license",
)
MODEL_KEYS = ("v3_e2", "community_forensics")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prepare_rows(manifest: Path, image_root: Path) -> tuple[list[dict], str]:
    manifest_bytes = manifest.read_bytes()
    root = image_root.resolve(strict=True)
    with manifest.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or set(reader.fieldnames) != set(FIELDS):
            raise ValueError(f"Manifest columns must be exactly: {', '.join(FIELDS)}")
        rows = list(reader)
    if not rows:
        raise ValueError("Manifest is empty")
    seen_paths: set[str] = set()
    seen_hashes: set[str] = set()
    prepared = []
    for row in rows:
        relative = Path(row["path"])
        file_path = (root / relative).resolve(strict=True)
        if not file_path.is_relative_to(root) or not file_path.is_file():
            raise ValueError(f"Image is outside image root: {row['path']}")
        if row["path"] in seen_paths:
            raise ValueError(f"Duplicate manifest path: {row['path']}")
        seen_paths.add(row["path"])
        if row["known_origin"] not in {"fake", "real"}:
            raise ValueError(f"Invalid known_origin for {row['path']}")
        for field in ("source_id", "category", "source_url", "license"):
            if not row[field].strip():
                raise ValueError(f"Missing {field} for {row['path']}")
        if row["known_origin"] == "fake" and not row["generator"].strip():
            raise ValueError(f"Missing generator for {row['path']}")
        image_bytes = file_path.read_bytes()
        actual_hash = digest(image_bytes)
        if actual_hash != row["sha256"].lower():
            raise ValueError(f"SHA-256 mismatch for {row['path']}")
        if actual_hash in seen_hashes:
            raise ValueError(f"Duplicate image bytes: {row['path']}")
        seen_hashes.add(actual_hash)
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
        prepared.append({**row, "original_bytes": image_bytes})
    return prepared, digest(manifest_bytes)


def jpeg90(data: bytes) -> bytes:
    """Apply one declared, identical JPEG encoding to both classes."""
    with Image.open(BytesIO(data)) as image:
        rgb = ImageOps.exif_transpose(image).convert("RGB")
        output = BytesIO()
        rgb.save(output, format="JPEG", quality=90, subsampling=0)
    return output.getvalue()


def metrics(results: list[dict], model_key: str) -> dict:
    counts = {"tp": 0, "fn": 0, "fp": 0, "tn": 0, "errors": 0}
    for row in results:
        model = next(item for item in row["models"] if item["model_key"] == model_key)
        if model["status"] != "success":
            counts["errors"] += 1
            continue
        known, predicted = row["known_origin"], model["prediction"]
        name = {
            ("fake", "fake"): "tp", ("fake", "real"): "fn",
            ("real", "fake"): "fp", ("real", "real"): "tn",
        }[(known, predicted)]
        counts[name] += 1
    ai_total = counts["tp"] + counts["fn"]
    real_total = counts["tn"] + counts["fp"]
    ai_recall = counts["tp"] / ai_total if ai_total else None
    real_recall = counts["tn"] / real_total if real_total else None
    counts["balanced_accuracy_on_successful_rows"] = (
        (ai_recall + real_recall) / 2
        if ai_recall is not None and real_recall is not None else None
    )
    counts["real_false_positive_rate_on_successful_rows"] = (
        counts["fp"] / real_total if real_total else None
    )
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variant", choices=("original", "jpeg90"), default="original")
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    try:
        rows, manifest_hash = prepare_rows(args.manifest, args.image_root)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    results = []
    with TestClient(app) as client:
        for index, row in enumerate(rows, 1):
            data = row.pop("original_bytes")
            if args.variant == "jpeg90":
                data = jpeg90(data)
            filename = Path(row["path"]).name
            mime = "image/jpeg" if args.variant == "jpeg90" else (
                "image/png" if filename.lower().endswith(".png") else "image/jpeg"
            )
            response = client.post(
                "/api/analyze/compare",
                data={"models": list(MODEL_KEYS)},
                files={"file": (filename, data, mime)},
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"API rejected {row['path']}: {response.status_code} {response.text}"
                )
            body = response.json()
            if [model["model_key"] for model in body["models"]] != list(MODEL_KEYS):
                raise RuntimeError(f"Unexpected model response for {row['path']}")
            results.append({
                **row,
                "evaluated_sha256": digest(data),
                "image_format": body["image_format"],
                "models": body["models"],
            })
            print(f"{index}/{len(rows)} {row['source_id']}", flush=True)

    report = {
        "purpose": "paired diagnostic; sample and source overlap limits apply",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": manifest_hash,
        "variant": args.variant,
        "model_keys": MODEL_KEYS,
        "models": {
            "v3_e2": {
                "id": E2_ID, "revision": E2_REVISION,
                "artifact_sha256": ARTIFACT_SHA256,
                "backbone_sha256": MOBILE_WEIGHT_SHA256,
            },
            "community_forensics": {
                "id": BASELINE_ID, "revision": BASELINE_REVISION,
            },
        },
        "sample_count": len(results),
        "metrics": {key: metrics(results, key) for key in MODEL_KEYS},
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
