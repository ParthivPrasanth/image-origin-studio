import base64
import hashlib
from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.model import IMAGE_MEAN, IMAGE_STD, input_view, preprocess
from app.v3_e2 import image_view, mobile_input_tensor, mobile_input_view


def sample(format_name="PNG"):
    image = Image.new("RGB", (91, 47))
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            pixels[x, y] = (x * 2 % 256, y * 4 % 256, (x + y) * 2 % 256)
    output = BytesIO()
    image.save(output, format=format_name)
    return output.getvalue()


def inspect(data, models=("v3_e2", "community_forensics")):
    return TestClient(app).post(
        "/api/inspect", data={"models": list(models)},
        files={"file": ("input.png", data, "image/png")},
    )


def decoded(view):
    encoded = view["preview_data_url"].removeprefix("data:image/png;base64,")
    with Image.open(BytesIO(base64.b64decode(encoded))) as source:
        return source.copy()


def test_inspector_has_original_metadata_and_selected_model_views():
    data = sample()
    response = inspect(data, ("community_forensics",))
    assert response.status_code == 200
    body = response.json()
    assert body["input"] == {
        "sha256": hashlib.sha256(data).hexdigest(),
        "width": 91, "height": 47, "image_format": "PNG",
    }
    assert [view["key"] for view in body["views"]] == ["original", "community_forensics"]
    model_view = body["views"][1]
    assert model_view["recipe_id"]
    assert decoded(model_view).tobytes() == input_view(data).tobytes()


def test_v3_views_match_shared_inference_inputs():
    data = sample()
    response = inspect(data, ("v3_e2",))
    assert response.status_code == 200
    views = {view["key"]: view for view in response.json()["views"]}
    square = image_view(data)
    assert decoded(views["v3_e2_fft"]).tobytes() == square.tobytes()
    assert decoded(views["v3_e2_mobile"]).tobytes() == mobile_input_view(square).tobytes()


def test_mobile_tensor_matches_torchvision_preset_exactly():
    from torchvision.models import MobileNet_V3_Small_Weights

    square = image_view(sample())
    preset = MobileNet_V3_Small_Weights.IMAGENET1K_V1.transforms()
    assert np.array_equal(
        mobile_input_tensor(square, preset).numpy(),
        preset(square.convert("RGB")).numpy(),
    )


def test_community_tensor_uses_exact_display_pixels():
    data = sample()
    view = input_view(data)
    expected = (np.asarray(view, dtype=np.float32) / 255 - IMAGE_MEAN) / IMAGE_STD
    np.testing.assert_array_equal(preprocess(data)[0], expected.transpose((2, 0, 1)))


def test_inspect_rejects_bad_files_and_model_selection():
    assert inspect(b"broken").status_code == 400
    assert inspect(sample(), ("unknown",)).status_code == 422
    assert inspect(b"x" * (10 * 1024 * 1024 + 1)).status_code == 413


@pytest.mark.parametrize("format_name", ["JPEG", "PNG", "WEBP"])
def test_supported_formats_inspect_without_loading_a_model(format_name, monkeypatch):
    from app import main

    monkeypatch.setattr(
        main, "get_detector", lambda: (_ for _ in ()).throw(AssertionError("model loaded")),
    )
    data = sample(format_name)
    response = inspect(data, ("community_forensics",))
    assert response.status_code == 200
    assert response.json()["input"]["image_format"] == format_name
