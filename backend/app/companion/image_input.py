"""Validation and normalization for user-supplied companion images."""
from __future__ import annotations

import base64
import binascii
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_ENCODED_CHARS = 28_000_000
MAX_DECODED_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_EDGE = 1600


class ImageInputError(ValueError):
    """A safe, user-actionable image validation failure."""


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    mime: str
    width: int
    height: int


def prepare_image(frame: str, claimed_mime: str) -> PreparedImage:
    """Decode, verify, orient, resize, and normalize an image to JPEG.

    Validation is repeated on the backend even though the renderer already
    compresses images. Renderer input is untrusted IPC/network data.
    """
    if claimed_mime not in ALLOWED_MIME_TYPES:
        raise ImageInputError("Use a PNG, JPEG, WebP, or GIF image.")
    if not frame or len(frame) > MAX_ENCODED_CHARS:
        raise ImageInputError("The image is empty or too large.")

    try:
        raw = base64.b64decode(frame, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageInputError("The image data is invalid.") from exc
    if not raw or len(raw) > MAX_DECODED_BYTES:
        raise ImageInputError("Images must be smaller than 20 MB.")

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            width, height = probe.size
            detected_format = (probe.format or "").upper()
            if detected_format not in {"PNG", "JPEG", "WEBP", "GIF"}:
                raise ImageInputError("The image format is not supported.")
            if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
                raise ImageInputError("The image dimensions are too large.")
            probe.verify()

        with Image.open(io.BytesIO(raw)) as source:
            source.seek(0)
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=84, optimize=True)
            normalized = output.getvalue()
            return PreparedImage(normalized, "image/jpeg", image.width, image.height)
    except ImageInputError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageInputError("The file is not a valid image.") from exc


def vision_capability(settings) -> tuple[bool, str | None]:
    """Return whether the configured provider can truthfully accept images."""
    if not settings.companion_vision_enabled:
        return False, "Image understanding is disabled in Settings."

    provider = settings.companion_vision_provider
    if provider == "local":
        return False, "The local vision provider is not implemented. Choose a multimodal cloud model."

    key_by_provider = {
        "nvidia": settings.companion_vision_api_key or settings.nvidia_api_key,
        "openai": settings.companion_vision_api_key or settings.openai_api_key,
        "openrouter": settings.companion_vision_api_key or settings.openrouter_api_key,
        "gemini": settings.companion_vision_api_key or settings.gemini_api_key or settings.openrouter_api_key,
    }
    if provider not in key_by_provider:
        return False, f"Vision provider '{provider}' is not supported."
    if not key_by_provider[provider]:
        return False, f"Configure an API key for the {provider} vision provider."
    return True, None
