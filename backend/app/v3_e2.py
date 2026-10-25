"""Inference-only copy of the owner's locked V3 E2 FFT/MobileNet fusion model.

The source recipe lives in the separate ML Project. This module reads only
hash-checked numeric tensors; it does not unpickle a training artifact or fit
any parameters. The ImageNet MobileNet weights are fetched from TorchVision's
published URL into the ignored model cache, then verified before loading.
"""

from __future__ import annotations

import hashlib
import math
import os
import tempfile
import urllib.request
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock

import numpy as np
from PIL import Image, ImageOps

from .model import Scores

MODEL_ID = "owner-trained-v3-e2"
MODEL_REVISION = "v3-e2-e560a8a20a84"
SCORE_THRESHOLD = 0.5
FFT_RECIPE = "v3-e2-exif-rgb-center-square-lanczos224-fft64-v1"
MOBILE_RECIPE = "v3-e2-square224-mobile-v3-small-imagenet1k-v1"
ARTIFACT_SHA256 = "7b18530b038cac4332095b00bf04690e91c79c15d0ae9acfe32d22187852fa5c"
MOBILE_WEIGHT_SHA256 = "047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f"
MOBILE_WEIGHT_URL = "https://download.pytorch.org/models/mobilenet_v3_small-047dcff4.pth"
ARTIFACT_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "v3_e2.npz"
DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "model-cache"
MOBILE_FILENAME = "mobilenet_v3_small-047dcff4.pth"
MOBILE_WEIGHT_BYTES = 10_306_551


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _weight_path() -> Path:
    cache = Path(os.environ.get("IMAGE_DETECTOR_MODEL_CACHE", DEFAULT_CACHE))
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / MOBILE_FILENAME
    if not path.exists():
        # A unique temporary file avoids leaving a partial checkpoint on failure.
        with tempfile.NamedTemporaryFile(dir=cache, suffix=".download", delete=False) as temp:
            temporary = Path(temp.name)
        try:
            with urllib.request.urlopen(MOBILE_WEIGHT_URL, timeout=60) as response:
                with temporary.open("wb") as handle:
                    total = 0
                    while chunk := response.read(1024 * 1024):
                        total += len(chunk)
                        if total > MOBILE_WEIGHT_BYTES:
                            raise RuntimeError("Downloaded MobileNet weights exceed the pinned size")
                        handle.write(chunk)
            if total != MOBILE_WEIGHT_BYTES or sha256(temporary) != MOBILE_WEIGHT_SHA256:
                raise RuntimeError("Downloaded MobileNet weights differ from the pinned release")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    if path.stat().st_size != MOBILE_WEIGHT_BYTES or sha256(path) != MOBILE_WEIGHT_SHA256:
        raise RuntimeError("Cached MobileNet weights differ from the pinned release")
    return path


def image_view(image_bytes: bytes) -> Image.Image:
    """Match v2_data.process: EXIF transpose, center square, Lanczos 224."""
    with Image.open(BytesIO(image_bytes)) as source:
        rgb = ImageOps.exif_transpose(source).convert("RGB")
    side = min(rgb.size)
    left, top = (rgb.width - side) // 2, (rgb.height - side) // 2
    return rgb.crop((left, top, left + side, top + side)).resize(
        (224, 224), Image.Resampling.LANCZOS
    )


def mobile_input_view(image: Image.Image, transform=None) -> Image.Image:
    """Show the MobileNet RGB pixels before tensor conversion/normalization."""
    from torchvision.models import MobileNet_V3_Small_Weights
    from torchvision.transforms import functional as F

    preset = transform or MobileNet_V3_Small_Weights.IMAGENET1K_V1.transforms()
    resized = F.resize(
        image.convert("RGB"), preset.resize_size,
        interpolation=preset.interpolation, antialias=preset.antialias,
    )
    return F.center_crop(resized, preset.crop_size)


def mobile_input_tensor(image: Image.Image, transform=None):
    """Use the same display view for the model tensor, then preset normalization."""
    import torch
    from torchvision.models import MobileNet_V3_Small_Weights
    from torchvision.transforms import functional as F

    preset = transform or MobileNet_V3_Small_Weights.IMAGENET1K_V1.transforms()
    view = mobile_input_view(image, preset)
    tensor = F.convert_image_dtype(F.pil_to_tensor(view), dtype=torch.float)
    return F.normalize(tensor, mean=preset.mean, std=preset.std)


@lru_cache(maxsize=1)
def _radial_masks() -> tuple[np.ndarray, ...]:
    coordinates = np.arange(224) - 224 // 2
    yy, xx = np.meshgrid(coordinates, coordinates, indexing="ij")
    radius = np.hypot(xx, yy)
    edges = np.linspace(0, radius.max() + 1e-6, 17)
    return tuple((radius >= edges[index]) & (radius < edges[index + 1]) for index in range(16))


@lru_cache(maxsize=1)
def _orientation_masks() -> tuple[np.ndarray, ...]:
    coordinates = np.arange(224) - 224 // 2
    yy, xx = np.meshgrid(coordinates, coordinates, indexing="ij")
    radius = np.hypot(xx, yy)
    angle = np.mod(np.arctan2(yy, xx), np.pi)
    radius_edges = np.linspace(0, radius.max() + 1e-6, 9)
    angle_edges = np.linspace(0, np.pi, 5)
    masks = []
    for radial_index in range(8):
        radial = (radius >= radius_edges[radial_index]) & (
            radius < radius_edges[radial_index + 1]
        ) & (radius > 0)
        for angle_index in range(4):
            mask = radial & (angle >= angle_edges[angle_index]) & (
                angle < angle_edges[angle_index + 1]
            )
            if not np.any(mask):
                raise ValueError("Empty FFT orientation mask")
            masks.append(mask)
    return tuple(masks)


def fft64(image: Image.Image) -> np.ndarray:
    """The locked v2 FFT64 recipe: 16 means, 16 deviations, 32 sectors."""
    if image.size != (224, 224):
        raise ValueError("Expected a 224 x 224 image view")
    gray = np.asarray(image.convert("L"), dtype=np.float32) / np.float32(255)
    centered = gray - gray.mean()
    magnitude = np.abs(np.fft.fftshift(np.fft.fft2(centered)))
    spectrum = np.log1p(magnitude)
    rings = _radial_masks()
    values = [spectrum[mask].mean() for mask in rings]
    values += [spectrum[mask].std() for mask in rings]
    values += [spectrum[mask].mean() for mask in _orientation_masks()]
    result = np.asarray(values, dtype=np.float32)
    if result.shape != (64,) or not np.isfinite(result).all():
        raise ValueError("Unexpected FFT feature vector")
    return result


class _FusionHead:
    """Thin wrapper to avoid importing PyTorch at module import time."""

    @staticmethod
    def build():
        import torch

        class Network(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.frequency = torch.nn.Sequential(torch.nn.Linear(64, 32), torch.nn.ReLU())
                self.spatial = torch.nn.Sequential(torch.nn.Linear(848, 64), torch.nn.ReLU())
                self.head = torch.nn.Sequential(
                    torch.nn.Linear(96, 32), torch.nn.ReLU(),
                    torch.nn.Dropout(0.1), torch.nn.Linear(32, 1),
                )

            def forward(self, frequency, spatial):
                combined = torch.cat((self.frequency(frequency), self.spatial(spatial)), dim=1)
                return self.head(combined).squeeze(1)

        return Network()


class E2Detector:
    def __init__(self) -> None:
        import torch
        from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

        if sha256(ARTIFACT_PATH) != ARTIFACT_SHA256:
            raise RuntimeError("Packaged V3 E2 artifact checksum mismatch")
        with np.load(ARTIFACT_PATH, allow_pickle=False) as saved:
            arrays = {key: saved[key] for key in saved.files}
        for name, width in (("frequency", 64), ("spatial", 848)):
            mean, scale = arrays[f"{name}_mean"], arrays[f"{name}_scale"]
            if mean.shape != (width,) or scale.shape != (width,) or not (
                np.isfinite(mean).all() and np.isfinite(scale).all() and (scale > 0).all()
            ):
                raise RuntimeError(f"Invalid E2 {name} scaler")
        self.frequency_mean = arrays["frequency_mean"]
        self.frequency_scale = arrays["frequency_scale"]
        self.spatial_mean = arrays["spatial_mean"]
        self.spatial_scale = arrays["spatial_scale"]
        self.head = _FusionHead.build()
        expected = set(self.head.state_dict())
        keys = {key.removeprefix("state__") for key in arrays if key.startswith("state__")}
        if keys != expected:
            raise RuntimeError("Packaged E2 head tensors do not match its architecture")
        state = {key: torch.from_numpy(arrays[f"state__{key}"].copy()) for key in expected}
        self.head.load_state_dict(state, strict=True)
        self.head.eval()
        self.mobile = mobilenet_v3_small(weights=None)
        weights = torch.load(_weight_path(), map_location="cpu", weights_only=True)
        self.mobile.load_state_dict(weights, strict=True)
        self.mobile.eval()
        self.transform = MobileNet_V3_Small_Weights.IMAGENET1K_V1.transforms()
        self._inference_lock = Lock()

    def _spatial_features(self, image: Image.Image) -> np.ndarray:
        import torch

        pixels = mobile_input_tensor(image, self.transform).unsqueeze(0)
        with torch.inference_mode():
            x = pixels
            pooled = []
            for index, layer in enumerate(self.mobile.features):
                x = layer(x)
                if index in (5, 10):
                    channels = {5: 40, 10: 96}[index]
                    if x.shape[1] != channels:
                        raise RuntimeError("Unexpected MobileNet feature channels")
                    pooled.extend((x.mean(dim=(2, 3)), x.std(dim=(2, 3), unbiased=False)))
            final = self.mobile.avgpool(x).flatten(1)
            multiscale = torch.cat((*pooled, final), dim=1)
            features = multiscale.numpy().astype(np.float32, copy=False)
        if features.shape != (1, 848) or not np.isfinite(features).all():
            raise RuntimeError("Unexpected MobileNet feature vector")
        return features

    def predict(self, image_bytes: bytes) -> Scores:
        import torch

        image = image_view(image_bytes)
        frequency = fft64(image)[None, :]
        with self._inference_lock, torch.inference_mode():
            spatial = self._spatial_features(image)
            # StandardScaler stores float64 means/scales and converts to float32
            # after transform, as the original V3 prediction code did.
            frequency = ((frequency - self.frequency_mean) / self.frequency_scale).astype(np.float32)
            spatial = ((spatial - self.spatial_mean) / self.spatial_scale).astype(np.float32)
            logit = self.head(torch.from_numpy(frequency), torch.from_numpy(spatial))
            fake = float(torch.sigmoid(logit)[0].item())
        if not math.isfinite(fake):
            raise RuntimeError("E2 returned a non-finite model score")
        return Scores(label="fake" if fake >= SCORE_THRESHOLD else "real", fake=fake, real=1.0 - fake)


_detector: E2Detector | None = None
_load_lock = Lock()


def get_e2_detector() -> E2Detector:
    global _detector
    if _detector is None:
        with _load_lock:
            if _detector is None:
                _detector = E2Detector()
    return _detector
