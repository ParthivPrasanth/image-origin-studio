"""Export the locked V3 E2 inference tensors without a runtime pickle dependency.

Run with the ML Project's Python environment and pass its original artifact path.
The source project is read-only. Only E2's fitted scalers and trained head are
written to the destination NPZ; the ImageNet MobileNet weights are separate.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import joblib
import numpy as np


SOURCE_SHA256 = "e560a8a20a84e45ca096271ffdf3b590eb43d79cbe5fd28ed7f639591ad41e4b"
SOURCE_MANIFEST_SHA256 = "d8bf6c016760eb3bba9cda359f17ed1f2ce61d8bae7cd3dbda796283f89e20be"
MOBILE_WEIGHT_SHA256 = "047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package(source: Path, destination: Path) -> None:
    if sha256(source) != SOURCE_SHA256:
        raise ValueError("The V3 candidate artifact differs from the evaluation lock")
    # Only load the trusted, hash-checked artifact supplied by the owner.
    stored = joblib.load(source)
    if (stored["manifest_sha256"] != SOURCE_MANIFEST_SHA256 or
            stored["mobile_weight_sha256"] != MOBILE_WEIGHT_SHA256 or
            stored["candidate_specs"]["E2"] != {
                "head": "original", "frequency": "f64", "spatial": "s848",
                "augmentation": True,
            }):
        raise ValueError("The E2 artifact metadata differs from the locked recipe")
    artifact = stored["artifacts"]["E2"]
    if (artifact["kind"] != "fusion" or artifact["head"] != "original" or
            artifact["spatial_width"] != 848 or not artifact["augmentation"]):
        raise ValueError("Unexpected E2 architecture")
    arrays = {}
    for block, width in (("frequency", 64), ("spatial", 848)):
        scaler = artifact[f"{block}_scaler"]
        if scaler.n_features_in_ != width:
            raise ValueError(f"Unexpected {block} scaler width")
        arrays[f"{block}_mean"] = np.asarray(scaler.mean_, dtype=np.float64)
        arrays[f"{block}_scale"] = np.asarray(scaler.scale_, dtype=np.float64)
    for key, value in artifact["state"].items():
        arrays[f"state__{key}"] = value.detach().cpu().numpy()
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(destination, **arrays)
    print(f"Saved {destination} ({sha256(destination)})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    package(arguments.source, arguments.destination)
