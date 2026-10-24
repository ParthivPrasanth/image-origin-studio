"""Guard the evidence checks used before a paired model comparison."""

import csv
from io import BytesIO

import pytest
from PIL import Image

from scripts.compare_models import FIELDS, digest, metrics, prepare_rows


def image_bytes(color: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 16), color=color).save(output, format="PNG")
    return output.getvalue()


def write_manifest(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def sample_row(name, data, known):
    return {
        "path": name,
        "sha256": digest(data),
        "known_origin": known,
        "source_id": name,
        "category": "test",
        "generator": "fixture" if known == "fake" else "",
        "source_url": "https://example.org/source",
        "license": "test fixture",
    }


def test_manifest_checks_all_hashes_before_inference(tmp_path):
    fake = image_bytes("red")
    real = image_bytes("blue")
    (tmp_path / "fake.png").write_bytes(fake)
    (tmp_path / "real.png").write_bytes(real)
    manifest = tmp_path / "manifest.csv"
    rows = [sample_row("fake.png", fake, "fake"), sample_row("real.png", real, "real")]
    write_manifest(manifest, rows)
    prepared, manifest_hash = prepare_rows(manifest, tmp_path)
    assert len(prepared) == 2
    assert manifest_hash == digest(manifest.read_bytes())

    rows[1]["sha256"] = "0" * 64
    write_manifest(manifest, rows)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        prepare_rows(manifest, tmp_path)


def test_metrics_keep_failures_out_of_denominator():
    results = [
        {"known_origin": "fake", "models": [{"model_key": "v3_e2", "status": "success", "prediction": "fake"}]},
        {"known_origin": "real", "models": [{"model_key": "v3_e2", "status": "success", "prediction": "fake"}]},
        {"known_origin": "real", "models": [{"model_key": "v3_e2", "status": "error"}]},
    ]
    counts = metrics(results, "v3_e2")
    assert (counts["tp"], counts["fp"], counts["errors"]) == (1, 1, 1)
    assert counts["balanced_accuracy_on_successful_rows"] == 0.5
