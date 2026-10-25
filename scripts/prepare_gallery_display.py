"""Make an auditable gallery JPEG from a locally saved source image."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from PIL import Image, ImageOps


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("display", type=Path)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    display = args.display.resolve()
    if display.exists():
        parser.error(f"Output already exists: {display}")
    display.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        source_size = image.size
        transformed = ImageOps.exif_transpose(image).convert("RGB")
        transformed.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        display_size = transformed.size
        transformed.save(display, "JPEG", quality=88, subsampling=0, optimize=True)
    print(f"source={source} size={source_size} sha256={sha256(source)}")
    print(f"display={display} size={display_size} sha256={sha256(display)}")


if __name__ == "__main__":
    main()
