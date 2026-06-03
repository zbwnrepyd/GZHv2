"""Unified image candidate object for collection, scoring, and persistence."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageCandidate:
    company_name: str
    asset_key: str
    image_url: str
    source_page: str | None
    source_type: str

    title: str | None = None
    alt_text: str | None = None
    author: str | None = None
    license: str | None = None

    local_path: str | None = None

    width: int | None = None
    height: int | None = None
    file_size: int | None = None
    aspect_ratio: float | None = None

    quality_score: float = 0
    relevance_score: float = 0
    source_score: float = 0
    layout_score: float = 0
    copyright_score: float = 0
    freshness_score: float = 0
    final_score: float = 0

    reject_reason: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

