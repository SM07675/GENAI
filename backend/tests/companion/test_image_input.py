from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from app.companion.image_input import ImageInputError, prepare_image


def encoded_image(fmt: str = "PNG", size: tuple[int, int] = (32, 24)) -> str:
    output = io.BytesIO()
    Image.new("RGB", size, (30, 120, 220)).save(output, format=fmt)
    return base64.b64encode(output.getvalue()).decode("ascii")


@pytest.mark.parametrize(
    ("fmt", "mime"),
    [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp"), ("GIF", "image/gif")],
)
def test_prepare_image_accepts_supported_formats(fmt: str, mime: str):
    result = prepare_image(encoded_image(fmt), mime)
    assert result.mime == "image/jpeg"
    assert result.width == 32
    assert result.height == 24
    assert result.data.startswith(b"\xff\xd8")


def test_prepare_image_resizes_large_dimensions():
    result = prepare_image(encoded_image(size=(2400, 1200)), "image/png")
    assert result.width == 1600
    assert result.height == 800


def test_prepare_image_rejects_invalid_base64():
    with pytest.raises(ImageInputError, match="invalid"):
        prepare_image("not-base64!", "image/png")


def test_prepare_image_rejects_unsupported_mime():
    with pytest.raises(ImageInputError, match="PNG, JPEG"):
        prepare_image(encoded_image(), "image/svg+xml")


def test_prepare_image_rejects_non_image_bytes():
    payload = base64.b64encode(b"this is not an image").decode("ascii")
    with pytest.raises(ImageInputError, match="valid image"):
        prepare_image(payload, "image/png")
