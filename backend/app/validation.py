"""Server-side upload checks; browser checks are only a convenience."""

from io import BytesIO

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 25_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


async def read_valid_image(upload: UploadFile) -> tuple[bytes, str]:
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_BYTES:
            raise HTTPException(status_code=413, detail="Image exceeds the 10 MB limit.")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="Choose a non-empty image.")
    try:
        with Image.open(BytesIO(data)) as image:
            image_format = image.format
            width, height = image.size
            if image_format not in ALLOWED_FORMATS:
                raise HTTPException(
                    status_code=415, detail="Use a JPEG, PNG, or WebP image."
                )
            if width * height > MAX_PIXELS:
                raise HTTPException(status_code=413, detail="Image has too many pixels.")
            image.verify()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(status_code=400, detail="Image is corrupt or unsupported.") from None
    return data, str(image_format)
