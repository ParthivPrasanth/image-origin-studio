from io import BytesIO

import numpy as np
from PIL import Image

from app.model import RAW_LOGIT_BOUNDARY, SCORE_THRESHOLD, preprocess, score_logit


def test_published_decision_boundary_is_used():
    below = score_logit(RAW_LOGIT_BOUNDARY - 0.001)
    at = score_logit(RAW_LOGIT_BOUNDARY)
    assert below.label == "real"
    assert at.label == "fake"
    assert abs(at.fake - SCORE_THRESHOLD) < 0.001
    assert abs(at.fake + at.real - 1.0) < 1e-12


def test_preprocess_shape_and_white_pixel_normalization():
    image = Image.new("RGB", (600, 400), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    tensor = preprocess(buffer.getvalue())
    assert tensor.shape == (1, 3, 384, 384)
    assert tensor.dtype == np.float32
    expected = (np.ones(3) - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    np.testing.assert_allclose(tensor[0, :, 0, 0], expected, atol=1e-5)
