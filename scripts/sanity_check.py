"""Run a transparent, small known-origin smoke check; not an accuracy benchmark."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.model import MODEL_ID, MODEL_REVISION, get_detector  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="CSV with path,known_origin,source,note")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    with args.manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not {"path", "known_origin", "source"}.issubset(rows[0]):
        parser.error("Manifest needs path, known_origin, and source columns and at least one row")

    started = perf_counter()
    detector = get_detector()
    startup_seconds = round(perf_counter() - started, 3)
    results = []
    for row in rows:
        if row["known_origin"] not in {"fake", "real"}:
            parser.error("known_origin must be fake or real")
        image_path = Path(row["path"])
        data = image_path.read_bytes()
        started = perf_counter()
        prediction = detector.predict(data)
        results.append({
            "source": row["source"],
            "note": row.get("note", ""),
            "sha256": hashlib.sha256(data).hexdigest(),
            "known_origin": row["known_origin"],
            "prediction": prediction.label,
            "fake_model_score": round(prediction.fake, 6),
            "real_model_score": round(prediction.real, 6),
            "inference_seconds": round(perf_counter() - started, 3),
        })
    report = {"model_id": MODEL_ID, "model_revision": MODEL_REVISION,
              "startup_seconds": startup_seconds,
              "startup_note": "Includes model download when cache is empty",
              "purpose": "sanity check, not benchmark",
              "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
