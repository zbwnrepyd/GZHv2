"""Path and URL segment safety helpers."""
from __future__ import annotations

import re


def safe_path_segment(value, default: str = "company") -> str:
    """Return one filesystem-safe path segment while preserving readable Unicode."""
    segment = str(value or default).strip()
    segment = segment.replace("/", "_").replace("\\", "_")
    segment = re.sub(r"\s+", "_", segment)
    segment = re.sub(r"[\x00-\x1f\x7f?%*:|\"<>]", "_", segment)
    while ".." in segment:
        segment = segment.replace("..", "_")
    segment = re.sub(r"_+", "_", segment)
    return segment.strip("._ ") or default
