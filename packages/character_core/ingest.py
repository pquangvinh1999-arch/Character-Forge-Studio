"""Validate uploaded PNG and GIF bytes before non-destructive storage."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
GIF87_MAGIC = b"GIF87a"
GIF89_MAGIC = b"GIF89a"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB ceiling


def validate_upload_bytes(filename: str, data: bytes) -> dict[str, Any]:
    """Validate that raw uploaded bytes are a valid PNG or GIF image."""
    if not data:
        raise ValueError("Uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Uploaded file exceeds {MAX_UPLOAD_BYTES} bytes limit.")

    if data.startswith(PNG_MAGIC):
        detected_format = "PNG"
        default_ext = ".png"
    elif data.startswith((GIF87_MAGIC, GIF89_MAGIC)):
        detected_format = "GIF"
        default_ext = ".gif"
    else:
        raise ValueError("Unsupported file signature: only PNG and GIF files are accepted.")

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        with Image.open(io.BytesIO(data)) as img2:
            width, height = img2.size
            n_frames = int(getattr(img2, "n_frames", 1))
    except Exception as exc:
        raise ValueError(f"Corrupt or unreadable {detected_format} file: {exc}") from exc

    safe_stem = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in Path(filename or "sprite").stem).strip("._")
    if not safe_stem:
        safe_stem = "character"
    safe_filename = f"{safe_stem}{default_ext}"

    return {
        "format": detected_format,
        "safe_filename": safe_filename,
        "safe_stem": safe_stem,
        "width": int(width),
        "height": int(height),
        "frame_count": n_frames,
        "size_bytes": len(data),
    }
