"""Core character asset ingestion, GIF frame extraction, and pixel coordinate math."""

from packages.character_core.coords import (
    canvas_point_to_source_pixel,
    canvas_rect_to_source_box,
    client_to_canvas_coords,
    inspect_pixel_at,
    source_box_to_canvas_rect,
    validate_selection_box,
)
from packages.character_core.gif_extractor import ExtractedAsset, ExtractedFrame, extract_frames_from_file
from packages.character_core.ingest import validate_upload_bytes

__all__ = [
    "ExtractedAsset",
    "ExtractedFrame",
    "canvas_point_to_source_pixel",
    "canvas_rect_to_source_box",
    "client_to_canvas_coords",
    "extract_frames_from_file",
    "inspect_pixel_at",
    "source_box_to_canvas_rect",
    "validate_selection_box",
    "validate_upload_bytes",
]
