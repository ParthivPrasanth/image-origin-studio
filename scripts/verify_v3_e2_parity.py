"""Read-only parity check against saved V3 E2 on already-viewed final images.

Run with the ML Project virtual environment. This reads source images and the
locked artifact but writes no files there and makes no new accuracy claim.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import joblib
import numpy as np


def main(source_root: Path) -> None:
    app_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(source_root / "scripts"))
    sys.path.insert(0, str(app_root / "backend"))

    from app.v3_e2 import E2Detector, fft64
    from v2_frequency_features import extract_fft64_from_image
    from v2_spatial_features import FrozenSpatialEncoder
    from v2_train_compare import image_view
    from v3_features import read_rows
    from v3_train_compare import predict

    artifact_path = source_root / "outputs/v3/candidate_artifacts.joblib"
    expected_hash = "e560a8a20a84e45ca096271ffdf3b590eb43d79cbe5fd28ed7f639591ad41e4b"
    if hashlib.sha256(artifact_path.read_bytes()).hexdigest() != expected_hash:
        raise RuntimeError("Source V3 artifact differs from the evaluation lock")
    artifact = joblib.load(artifact_path)["artifacts"]["E2"]
    original_mobile = FrozenSpatialEncoder(device="cpu")
    packaged = E2Detector()
    rows = read_rows("final_test")[:4]
    differences = []
    for row in rows:
        source_path = source_root / row["processed_path"]
        image = image_view(row, "clean")
        original_frequency = extract_fft64_from_image(image)
        original_spatial = original_mobile.encode_images([image])[1]
        data = {"f64": original_frequency[None, :], "s848": original_spatial}
        expected = float(predict("E2", artifact, data)[0])
        view = packaged.predict(source_path.read_bytes())
        actual = view.fake
        np.testing.assert_array_equal(fft64(image), original_frequency)
        np.testing.assert_allclose(packaged._spatial_features(image), original_spatial, rtol=0, atol=1e-6)
        if abs(expected - actual) > 1e-6 or view.label != ("fake" if expected >= 0.5 else "real"):
            raise AssertionError(f"Parity failed for {row['row_id']}: {expected} vs {actual}")
        differences.append(abs(expected - actual))
    print(f"V3 E2 parity passed on {len(rows)} locked final images; max score difference {max(differences):.2g}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    args = parser.parse_args()
    main(args.source_root)
