"""Record pinned model suggestions for curated gallery candidates.

This is a product demonstration run, not an accuracy evaluation. It never
reads origin labels, fits thresholds, or reports aggregate performance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "frontend" / "public" / "gallery" / "candidates"
MODEL_KEYS = ("v3_e2", "community_forensics")


def score_assets(names: list[str]) -> list[dict]:
    asset_root = ASSET_ROOT.resolve(strict=True)
    if not names:
        raise ValueError("Choose at least one candidate filename")
    if len(names) != len(set(names)):
        raise ValueError("Candidate filenames must be unique")
    seen_hashes: set[str] = set()
    records = []
    with TestClient(app) as client:
        for name in names:
            file_path = (asset_root / name).resolve(strict=True)
            if not file_path.is_relative_to(asset_root) or not file_path.is_file():
                raise ValueError(f"Candidate is outside the gallery asset folder: {name}")
            data = file_path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen_hashes:
                raise ValueError(f"Duplicate candidate bytes: {name}")
            seen_hashes.add(digest)
            response = client.post(
                "/api/analyze/compare",
                data={"models": list(MODEL_KEYS)},
                files={"file": (file_path.name, data, "application/octet-stream")},
            )
            if response.status_code != 200:
                raise RuntimeError(f"{name}: API status {response.status_code}: {response.text}")
            body = response.json()
            if body["input"]["sha256"] != digest:
                raise RuntimeError(f"{name}: API hash differs from the display asset")
            if any(entry["status"] != "success" for entry in body["models"]):
                raise RuntimeError(f"{name}: one or both pinned models failed")
            records.append({
                "candidate_file": name,
                "display_sha256": digest,
                "analyzed_at": body["analyzed_at"],
                "input": body["input"],
                "model_suggestions": body["models"],
            })
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", action="append", required=True,
                        help="Candidate filename inside frontend/public/gallery/candidates")
    parser.add_argument("--output", type=Path, required=True,
                        help="New JSON file for per-image suggestions; existing files are refused")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error(f"Output already exists: {output}")
    records = score_assets(args.asset)
    payload = {
        "purpose": "curated gallery demonstration, not an accuracy benchmark",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "assets": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    print(f"Recorded {len(records)} individual candidate suggestions in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
