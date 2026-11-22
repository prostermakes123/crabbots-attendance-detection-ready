import base64

import cv2
import numpy as np
import pytest

from backend.app.services.images import (
    ImageValidationError,
    decode_data_url,
    decode_image_bytes,
)


def _jpeg_bytes() -> bytes:
    image = np.full((96, 96, 3), 127, dtype=np.uint8)
    ok, encoded = cv2.imencode('.jpg', image)
    assert ok
    return encoded.tobytes()


def test_decode_image_bytes_returns_bgr_image():
    decoded = decode_image_bytes(_jpeg_bytes())
    assert decoded.shape == (96, 96, 3)
    assert decoded.dtype == np.uint8


def test_decode_image_rejects_empty_and_non_image_payloads():
    with pytest.raises(ImageValidationError, match='empty'):
        decode_image_bytes(b'')
    with pytest.raises(ImageValidationError, match='decode'):
        decode_image_bytes(b'not an image')


def test_decode_data_url_accepts_valid_jpeg():
    payload = base64.b64encode(_jpeg_bytes()).decode('ascii')
    decoded = decode_data_url(f'data:image/jpeg;base64,{payload}')
    assert decoded.shape == (96, 96, 3)


def test_decode_data_url_rejects_non_image_mime_and_oversized_payload():
    with pytest.raises(ImageValidationError, match='Only base64'):
        decode_data_url('data:text/html;base64,PGh0bWw+')
    with pytest.raises(ImageValidationError, match='larger'):
        decode_data_url('A' * 200, max_mb=0.00001)
