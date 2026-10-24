from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.main import app
from app.model import MODEL_REVISION, SCORE_THRESHOLD, Scores


class FakeDetector:
    def predict(self, image_bytes: bytes) -> Scores:
        assert image_bytes
        return Scores(label="fake", fake=0.8, real=0.2)


def png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 16), color="red").save(output, format="PNG")
    return output.getvalue()


def large_dimension_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (5001, 5000), color="red").save(output, format="PNG")
    return output.getvalue()


client = TestClient(app)


def setup_module():
    main.get_detector = lambda: FakeDetector()


def test_valid_image_returns_both_scores_and_revision():
    response = client.post("/api/analyze", files={"file": ("test.png", png(), "image/png")})
    assert response.status_code == 200
    result = response.json()
    assert result["prediction"] == "fake"
    assert result["model_scores"] == {"fake": 0.8, "real": 0.2}
    assert result["model_revision"] == MODEL_REVISION
    assert result["ai_score_threshold"] == SCORE_THRESHOLD


def test_corrupt_image_is_rejected():
    response = client.post("/api/analyze", files={"file": ("bad.png", b"not an image", "image/png")})
    assert response.status_code == 400
    assert "corrupt" in response.json()["detail"].lower()


def test_file_size_limit():
    response = client.post("/api/analyze", files={"file": ("big.png", b"x" * (10 * 1024 * 1024 + 1), "image/png")})
    assert response.status_code == 413


def test_pixel_limit_even_when_file_is_small():
    response = client.post(
        "/api/analyze", files={"file": ("huge.png", large_dimension_png(), "image/png")}
    )
    assert response.status_code == 413


def test_content_is_checked_instead_of_filename():
    response = client.post(
        "/api/analyze", files={"file": ("misleading.jpg", png(), "image/jpeg")}
    )
    assert response.status_code == 200
    assert response.json()["image_format"] == "PNG"
