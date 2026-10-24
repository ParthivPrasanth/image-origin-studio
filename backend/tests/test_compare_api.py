from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.model import MODEL_REVISION, Scores
from app.v3_e2 import MODEL_REVISION as E2_REVISION


class FakeDetector:
    def __init__(self, fake: float):
        self.fake = fake

    def predict(self, image_bytes: bytes) -> Scores:
        assert image_bytes
        return Scores(
            label="fake" if self.fake >= 0.5 else "real",
            fake=self.fake,
            real=1 - self.fake,
        )


class FailedDetector:
    def predict(self, image_bytes: bytes) -> Scores:
        raise RuntimeError("Private inference error")


def png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 16), color="red").save(output, format="PNG")
    return output.getvalue()


def post(models):
    return TestClient(main.app).post(
        "/api/analyze/compare",
        data={"models": models},
        files={"file": ("test.png", png(), "image/png")},
    )


def test_both_models_return_separate_scores_and_revisions(monkeypatch):
    monkeypatch.setattr(main, "get_e2_detector", lambda: FakeDetector(0.8))
    monkeypatch.setattr(main, "get_detector", lambda: FakeDetector(0.3))
    response = post(["v3_e2", "community_forensics"])
    assert response.status_code == 200
    body = response.json()
    assert body["image_format"] == "PNG"
    assert [result["model_key"] for result in body["models"]] == [
        "v3_e2", "community_forensics"
    ]
    assert [result["status"] for result in body["models"]] == ["success", "success"]
    assert [result["prediction"] for result in body["models"]] == ["fake", "real"]
    assert [result["model_revision"] for result in body["models"]] == [
        E2_REVISION, MODEL_REVISION
    ]
    assert [result["ai_score_threshold"] for result in body["models"]] == [0.5, 0.65]


def test_single_model_selection_does_not_load_the_other(monkeypatch):
    monkeypatch.setattr(main, "get_e2_detector", lambda: FakeDetector(0.8))
    monkeypatch.setattr(
        main, "get_detector", lambda: (_ for _ in ()).throw(AssertionError("not selected"))
    )
    response = post("v3_e2")
    assert response.status_code == 200
    assert [result["model_key"] for result in response.json()["models"]] == ["v3_e2"]


def test_model_failure_preserves_other_result_and_hides_exception(monkeypatch):
    monkeypatch.setattr(main, "get_e2_detector", lambda: FailedDetector())
    monkeypatch.setattr(main, "get_detector", lambda: FakeDetector(0.3))
    response = post(["v3_e2", "community_forensics"])
    assert response.status_code == 200
    failures, success = response.json()["models"]
    assert failures["model_key"] == "v3_e2"
    assert failures["status"] == "error"
    assert "Private inference error" not in failures["error"]
    assert success["status"] == "success"


def test_all_requested_model_failures_are_returned(monkeypatch):
    monkeypatch.setattr(main, "get_e2_detector", lambda: FailedDetector())
    monkeypatch.setattr(main, "get_detector", lambda: FailedDetector())
    response = post(["v3_e2", "community_forensics"])
    assert response.status_code == 200
    assert [result["status"] for result in response.json()["models"]] == ["error", "error"]


def test_invalid_model_selection_is_rejected(monkeypatch):
    monkeypatch.setattr(main, "get_e2_detector", lambda: FakeDetector(0.8))
    assert post("unknown").status_code == 422
    assert post(["v3_e2", "v3_e2"]).status_code == 422
