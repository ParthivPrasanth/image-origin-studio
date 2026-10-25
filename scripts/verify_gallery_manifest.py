"""Check gallery review records against display assets and pinned model identities."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.model import MODEL_ID as BASELINE_ID  # noqa: E402
from app.model import MODEL_REVISION as BASELINE_REVISION  # noqa: E402
from app.model import SCORE_THRESHOLD as BASELINE_THRESHOLD  # noqa: E402
from app.v3_e2 import MODEL_ID as E2_ID  # noqa: E402
from app.v3_e2 import MODEL_REVISION as E2_REVISION  # noqa: E402
from app.v3_e2 import SCORE_THRESHOLD as E2_THRESHOLD  # noqa: E402

MANIFEST = ROOT / "docs" / "GALLERY_MANIFEST.json"
ASSET_ROOT = ROOT / "frontend" / "public" / "gallery" / "candidates"
MODEL_EXPECTATIONS = {
    "v3_e2": (E2_ID, E2_REVISION, E2_THRESHOLD),
    "community_forensics": (BASELINE_ID, BASELINE_REVISION, BASELINE_THRESHOLD),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(manifest.get("status") == "local-review-draft", "Gallery status must remain local review draft")
    cases = manifest.get("cases")
    require(isinstance(cases, list) and 8 <= len(cases) <= 12, "Gallery needs 8-12 cases")
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    asset_root = ASSET_ROOT.resolve(strict=True)
    for case in cases:
        case_id = case.get("id")
        require(isinstance(case_id, str) and case_id and case_id not in seen_ids,
                f"Duplicate or missing case id: {case_id}")
        seen_ids.add(case_id)
        require(case.get("origin") in {"camera_photo", "ai_generated"},
                f"{case_id}: invalid origin")
        for field in ("title", "sourceName", "attribution", "originEvidence", "rights", "edits"):
            require(isinstance(case.get(field), str) and case[field].strip(),
                    f"{case_id}: missing {field}")
        source = case.get("sourcePage", "")
        parsed = urlparse(source)
        require(parsed.scheme == "https" and bool(parsed.netloc),
                f"{case_id}: source page must be HTTPS")
        rights_url = case.get("rightsUrl")
        if rights_url is not None:
            license_page = urlparse(rights_url)
            require(license_page.scheme == "https" and bool(license_page.netloc),
                    f"{case_id}: license link must be HTTPS")
        asset_url = case.get("assetUrl", "")
        require(asset_url.startswith("/gallery/candidates/"),
                f"{case_id}: asset URL must use the candidate folder")
        filename = unquote(asset_url.removeprefix("/gallery/candidates/"))
        asset = (asset_root / filename).resolve(strict=True)
        require(asset.is_relative_to(asset_root) and asset.is_file(),
                f"{case_id}: asset path escapes candidate folder")
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        require(case.get("sha256") == digest and digest not in seen_hashes,
                f"{case_id}: display hash mismatch or duplicate bytes")
        seen_hashes.add(digest)
        runs = case.get("modelRuns")
        require(isinstance(runs, list) and len(runs) == 2,
                f"{case_id}: expected both model suggestions")
        require({run.get("modelKey") for run in runs} == set(MODEL_EXPECTATIONS),
                f"{case_id}: expected each model exactly once")
        for run in runs:
            expected_id, expected_revision, expected_threshold = MODEL_EXPECTATIONS[run["modelKey"]]
            require(run.get("modelId") == expected_id and
                    run.get("modelRevision") == expected_revision and
                    run.get("threshold") == expected_threshold,
                    f"{case_id}: model identity or threshold changed")
            require(run.get("prediction") in {"fake", "real"} and
                    isinstance(run.get("aiScore"), (int, float)) and
                    0 <= run["aiScore"] <= 1,
                    f"{case_id}: invalid suggestion")
            require(bool(run.get("preprocessingRecipe")) and bool(run.get("analyzedAt")),
                    f"{case_id}: recipe or timestamp missing")
    print(f"Verified {len(cases)} draft gallery records and distinct display assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
