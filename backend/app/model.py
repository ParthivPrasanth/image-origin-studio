"""The credited Hugging Face model is loaded once per backend process."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from threading import Lock

from PIL import Image, ImageOps

MODEL_ID = "jacoballessio/ai-image-detect-distilled"
MODEL_REVISION = "4098d40c873a2e38404ea378a8284f33125bd90c"


@dataclass(frozen=True)
class Scores:
    label: str
    fake: float
    real: float


class Detector:
    def __init__(self) -> None:
        # Imports are delayed so validation and API tests do not download a model.
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        self.torch = torch
        self.processor = AutoImageProcessor.from_pretrained(
            MODEL_ID, revision=MODEL_REVISION, use_fast=False
        )
        self.model = AutoModelForImageClassification.from_pretrained(
            MODEL_ID, revision=MODEL_REVISION, use_safetensors=True
        )
        labels = {int(index): label.lower() for index, label in self.model.config.id2label.items()}
        if labels != {0: "fake", 1: "real"}:
            raise RuntimeError(f"Unexpected model labels: {labels}")
        self.model.eval()
        self._inference_lock = Lock()

    def predict(self, image_bytes: bytes) -> Scores:
        with Image.open(BytesIO(image_bytes)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        # A single process serializes CPU inference to avoid memory spikes.
        with self._inference_lock, self.torch.inference_mode():
            logits = self.model(**inputs).logits[0]
            probabilities = self.torch.softmax(logits, dim=-1).tolist()
        fake, real = (float(probabilities[0]), float(probabilities[1]))
        return Scores(label="fake" if fake >= real else "real", fake=fake, real=real)


_load_lock = Lock()
_detector: Detector | None = None


def get_detector() -> Detector:
    global _detector
    if _detector is None:
        with _load_lock:
            if _detector is None:
                _detector = Detector()
    return _detector
