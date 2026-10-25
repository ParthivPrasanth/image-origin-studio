"""Refresh the gallery with four public COCOXGEN examples and pinned runs."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "GALLERY_MANIFEST.json"
STAGE = ROOT / ".local" / "gallery-cocoxgen-stage.json"
SCORES = ROOT / ".local" / "gallery-cocoxgen-scores.json"

# id, title, source image number, prompt length, generator
SELECTED = (
    ("traffic-lights", "Traffic lights", "558558", "short", "sdxl"),
    ("skier", "Skier in snow", "445602", "long", "sdxl"),
    ("bananas", "Bananas on a chair", "279769", "short", "sdxl"),
    ("tennis-player", "Tennis player", "19432", "long", "fooocus"),
)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    camera = {case["id"]: case for case in manifest["cases"] if case["origin"] == "camera_photo"}
    if set(camera) != {"waterfall", "bird", "dunes", "bridge"}:
        raise SystemExit("Expected four existing USGS cases")
    stage = {entry["asset"]: entry for entry in json.loads(STAGE.read_text(encoding="utf-8"))}
    scores = {entry["candidate_file"]: entry for entry in json.loads(SCORES.read_text(encoding="utf-8"))["assets"]}
    generated = []
    for case_id, title, number, length, generator in SELECTED:
        filename = f"cocoxgen-{int(number):012d}-{generator}-{length}-display.jpg"
        source = stage[filename]
        scored = scores[filename]
        if source["display_sha256"] != scored["display_sha256"]:
            raise SystemExit(f"Display hash differs from scored image: {filename}")
        extension = "png" if generator == "fooocus" else "jpg"
        source_filename = f"{number}-{length}-{generator}.{extension}"
        source_page = "https://huggingface.co/datasets/heikeadel/cocoxgen"
        runs = []
        for run in scored["model_suggestions"]:
            if run["status"] != "success":
                raise SystemExit(f"Model run failed: {filename}")
            runs.append({
                "modelKey": run["model_key"],
                "modelId": run["model_id"],
                "modelRevision": run["model_revision"],
                "preprocessingRecipe": run["preprocessing_recipe"],
                "prediction": run["prediction"],
                "aiScore": run["model_scores"]["fake"],
                "threshold": run["ai_score_threshold"],
                "analyzedAt": scored["analyzed_at"],
            })
        generated.append({
            "id": case_id,
            "title": title,
            "assetUrl": f"/gallery/candidates/{filename}",
            "origin": "ai_generated",
            "sourcePage": source_page,
            "sourceName": f"COCOXGEN: {source_filename}",
            "attribution": "COCOXGEN by Philipp Moeßner and Heike Adel; generated with "
                           f"{source['generator']}. Display copy resized and re-encoded.",
            "originEvidence": "The public COCOXGEN dataset identifies this file as an "
                              f"{source['generator']} generated image. Dataset revision "
                              f"{source['source_revision'][:7]}; source SHA-256 "
                              f"{source['source_sha256']}.",
            "rights": "COCOXGEN dataset license: Creative Commons Attribution 4.0 International.",
            "rightsUrl": "https://creativecommons.org/licenses/by/4.0/",
            "edits": "Source image was EXIF-oriented, converted to RGB, resized to fit "
                     "1200 × 1200 with Lanczos, then re-encoded JPEG quality 88; no crop or retouch.",
            "sha256": source["display_sha256"],
            "modelRuns": runs,
        })
    manifest["cases"] = [
        generated[0], camera["waterfall"], generated[1], camera["bird"],
        generated[2], camera["dunes"], generated[3], camera["bridge"],
    ]
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Updated eight gallery cases with four public COCOXGEN images")


if __name__ == "__main__":
    main()
