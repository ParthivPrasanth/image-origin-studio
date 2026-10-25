"""Pinned whole-image detector loaded once per backend process."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from io import BytesIO
from threading import Lock

import numpy as np
from PIL import Image, ImageOps

MODEL_ID = "Thermostatic/community-forensics-frontier-detector-2026-08"
MODEL_REVISION = "16db135220b318d811b207db576d90368980b595"
MODEL_FILENAME = "community_forensics_frontier_fp16.onnx"
MODEL_SHA256 = "d75791ba2fa59146025d342cfaafa9ddeab24af117642a94f752ee4c1619375d"
RAW_LOGIT_BOUNDARY = 1.359375
CALIBRATION_INTERCEPT = -0.7403357915937764
SCORE_THRESHOLD = 0.65
IMAGE_MEAN = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
IMAGE_STD = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)
PREPROCESSING_RECIPE = "community-forensics-rgb-440-bicubic-center384-imagenet-v1"


@dataclass(frozen=True)
class Scores:
    label: str
    fake: float
    real: float


def input_view(image_bytes: bytes) -> Image.Image:
    """Return exact RGB pixels immediately before tensor normalization."""
    with Image.open(BytesIO(image_bytes)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    width, height = image.size
    if width < height:
        resized_width, resized_height = 440, int(440 * height / width)
    else:
        resized_width, resized_height = int(440 * width / height), 440
    image = image.resize((resized_width, resized_height), Image.Resampling.BICUBIC)
    left = round((resized_width - 384) / 2)
    top = round((resized_height - 384) / 2)
    return image.crop((left, top, left + 384, top + 384))


def preprocess(image_bytes: bytes) -> np.ndarray:
    """Apply the model card's RGB, 440-short-edge, center-crop preprocessing."""
    image = input_view(image_bytes)
    pixels = np.asarray(image, dtype=np.float32) / 255.0
    normalized = (pixels - IMAGE_MEAN) / IMAGE_STD
    return np.ascontiguousarray(np.transpose(normalized, (2, 0, 1))[None, ...])


def score_logit(raw_logit: float) -> Scores:
    """Keep the published raw decision boundary independent of score rounding."""
    calibrated_logit = raw_logit + CALIBRATION_INTERCEPT
    if calibrated_logit >= 0:
        exp_term = math.exp(-calibrated_logit)
        fake = 1.0 / (1.0 + exp_term)
    else:
        exp_term = math.exp(calibrated_logit)
        fake = exp_term / (1.0 + exp_term)
    return Scores(
        label="fake" if raw_logit >= RAW_LOGIT_BOUNDARY else "real",
        fake=fake,
        real=1.0 - fake,
    )


class Detector:
    def __init__(self) -> None:
        # Delay model download until the first analysis; tests can stub this class.
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download

        model_path = hf_hub_download(
            repo_id=MODEL_ID,
            filename=MODEL_FILENAME,
            revision=MODEL_REVISION,
        )
        digest = hashlib.sha256()
        with open(model_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != MODEL_SHA256:
            raise RuntimeError("Downloaded model checksum does not match the pinned release")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        self.session = ort.InferenceSession(
            model_path, sess_options=options, providers=["CPUExecutionProvider"]
        )
        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            raise RuntimeError("Unexpected ONNX model inputs or outputs")
        self.input_name = inputs[0].name
        self.output_name = outputs[0].name
        self._inference_lock = Lock()

    def predict(self, image_bytes: bytes) -> Scores:
        tensor = preprocess(image_bytes)
        with self._inference_lock:
            output = self.session.run([self.output_name], {self.input_name: tensor})[0]
        raw_logit = float(np.asarray(output).reshape(-1)[0])
        return score_logit(raw_logit)


_load_lock = Lock()
_detector: Detector | None = None


def get_detector() -> Detector:
    global _detector
    if _detector is None:
        with _load_lock:
            if _detector is None:
                _detector = Detector()
    return _detector
