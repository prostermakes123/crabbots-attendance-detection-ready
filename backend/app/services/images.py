"""Image/video decoding with strict size and format validation."""

from __future__ import annotations

import base64
import binascii

import cv2
import numpy as np

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_DIMENSION = 6000


class ImageValidationError(ValueError):
    pass


def decode_image_bytes(data: bytes, max_mb: float = 12.0) -> np.ndarray:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise ImageValidationError("Image payload must be bytes.")
    if not np.isfinite(max_mb) or max_mb <= 0:
        raise ImageValidationError("Image size limit must be positive.")
    if not data:
        raise ImageValidationError("The uploaded file is empty.")
    if len(data) > max_mb * 1024 * 1024:
        raise ImageValidationError(f"File is larger than the {max_mb:.0f} MB limit.")
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ImageValidationError("Could not decode this file as an image (use JPG, PNG or WebP).")
    h, w = image.shape[:2]
    if w < 64 or h < 64:
        raise ImageValidationError("Image is too small to analyse (minimum 64x64).")
    if max(h, w) > MAX_DIMENSION:
        scale = MAX_DIMENSION / max(h, w)
        image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return image


def decode_data_url(data_url: str, max_mb: float = 12.0) -> np.ndarray:
    if not isinstance(data_url, str) or not data_url:
        raise ImageValidationError("Missing image data.")
    if not np.isfinite(max_mb) or max_mb <= 0:
        raise ImageValidationError("Image size limit must be positive.")
    payload = data_url
    if data_url.startswith("data:"):
        header, separator, payload = data_url.partition(",")
        if not separator or not header.lower().startswith(("data:image/jpeg;base64", "data:image/jpg;base64", "data:image/png;base64", "data:image/webp;base64")):
            raise ImageValidationError("Only base64-encoded JPEG, PNG, or WebP frames are supported.")
    # Base64 expands data by roughly 4/3. Reject oversized payloads before decoding
    # so a hostile WebSocket message cannot force a large allocation.
    max_encoded = int(max_mb * 1024 * 1024 * 4 / 3) + 16
    if len(payload) > max_encoded:
        raise ImageValidationError(f"Image is larger than the {max_mb:.0f} MB limit.")
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageValidationError("Image payload is not valid base64.") from exc
    return decode_image_bytes(raw, max_mb=max_mb)


def encode_jpeg_base64(image: np.ndarray, quality: int = 82) -> str:
    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise ImageValidationError("Could not encode image.")
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def resize_max_width(image: np.ndarray, max_width: int) -> np.ndarray:
    h, w = image.shape[:2]
    if w <= max_width:
        return image
    scale = max_width / w
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
