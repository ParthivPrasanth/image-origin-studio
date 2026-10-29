"""Check a running Linux API against the saved local gallery model runs.

This is cross-platform inference parity, not an accuracy evaluation.
"""

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import httpx


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "GALLERY_MANIFEST.json"
PUBLIC = ROOT / "frontend" / "public"
MODEL_KEYS = ("v3_e2", "community_forensics")
MAX_SCORE_DRIFT = 1e-4


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    cases = json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]
    durations = []
    max_drift = 0.0

    with httpx.Client(base_url=args.url, timeout=120) as client:
        for case in cases:
            path = PUBLIC / case["assetUrl"].lstrip("/")
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest != case["sha256"]:
                raise AssertionError(f"{case['id']}: display-file hash changed")

            started = perf_counter()
            response = client.post(
                "/api/analyze/compare",
                data={"models": list(MODEL_KEYS)},
                files={"file": (path.name, data, "image/jpeg")},
            )
            durations.append(perf_counter() - started)
            response.raise_for_status()
            result = response.json()
            if result["input"]["sha256"] != digest:
                raise AssertionError(f"{case['id']}: API input hash differs")

            actual = {item["model_key"]: item for item in result["models"]}
            expected = {item["modelKey"]: item for item in case["modelRuns"]}
            if set(actual) != set(MODEL_KEYS):
                raise AssertionError(f"{case['id']}: missing model result")
            for key in MODEL_KEYS:
                got, saved = actual[key], expected[key]
                if got["status"] != "success":
                    raise AssertionError(f"{case['id']}/{key}: {got}")
                if got["model_revision"] != saved["modelRevision"]:
                    raise AssertionError(f"{case['id']}/{key}: revision changed")
                if got["prediction"] != saved["prediction"]:
                    raise AssertionError(f"{case['id']}/{key}: decision changed")
                drift = abs(got["model_scores"]["fake"] - saved["aiScore"])
                max_drift = max(max_drift, drift)
                if drift > MAX_SCORE_DRIFT:
                    raise AssertionError(f"{case['id']}/{key}: score drift {drift}")
            print(
                f"{case['id']}: "
                + ", ".join(f"{key}={actual[key]['prediction']}" for key in MODEL_KEYS)
                + f" ({durations[-1]:.3f} s)"
            )

    print(
        f"PASS {len(cases)} files, {len(cases) * len(MODEL_KEYS)} model results; "
        f"max score drift {max_drift:.8f}; total HTTP wall time {sum(durations):.3f} s"
    )


if __name__ == "__main__":
    main()
