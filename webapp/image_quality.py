"""Image inspection and hard quality filters."""
from __future__ import annotations

import os
from statistics import pstdev

from PIL import Image, ImageStat, UnidentifiedImageError

from image_candidate import ImageCandidate


MIN_WIDTH = 300
MIN_HEIGHT = 200
MIN_FILE_SIZE = 10 * 1024
MAX_FILE_SIZE = 8 * 1024 * 1024
LOGO_MIN_SIZE = 64


def inspect_local_image(candidate: ImageCandidate) -> ImageCandidate:
    """Populate size and format metadata from a downloaded local image."""
    if not candidate.local_path:
        candidate.reject_reason = "缺少本地图片路径"
        return candidate

    try:
        candidate.file_size = os.path.getsize(candidate.local_path)
        with Image.open(candidate.local_path) as img:
            candidate.width, candidate.height = img.size
            candidate.aspect_ratio = round(candidate.width / candidate.height, 4) if candidate.height else None
            candidate.meta["format"] = img.format or ""
    except (OSError, UnidentifiedImageError) as exc:
        candidate.reject_reason = f"图片无法打开: {exc}"
    return candidate


def validate_candidate(candidate: ImageCandidate) -> tuple[bool, str]:
    """Apply hard filters. Returns (passed, reason)."""
    if candidate.reject_reason:
        return False, candidate.reject_reason
    if not candidate.width or not candidate.height:
        return False, "缺少图片尺寸"

    if candidate.asset_key == "logo":
        if candidate.width < LOGO_MIN_SIZE or candidate.height < LOGO_MIN_SIZE:
            return False, "Logo 尺寸过小"
    else:
        if candidate.width < MIN_WIDTH or candidate.height < MIN_HEIGHT:
            return False, "尺寸过小"

    ratio = candidate.aspect_ratio or (candidate.width / candidate.height)
    if ratio > 6 or ratio < 0.25:
        return False, "比例极端"

    file_size = candidate.file_size or 0
    if file_size > MAX_FILE_SIZE:
        return False, "文件过大"
    if candidate.asset_key != "logo" and file_size < MIN_FILE_SIZE:
        return False, "文件过小"

    if _looks_like_tracking_pixel(candidate):
        return False, "疑似透明追踪像素"
    if candidate.asset_key != "logo" and _looks_like_solid_color(candidate):
        return False, "疑似纯色图"
    return True, ""


def _looks_like_tracking_pixel(candidate: ImageCandidate) -> bool:
    return (candidate.width or 0) <= 4 and (candidate.height or 0) <= 4


def _looks_like_solid_color(candidate: ImageCandidate) -> bool:
    if not candidate.local_path:
        return False
    try:
        with Image.open(candidate.local_path).convert("RGB") as img:
            sample = img.resize((24, 24))
            stat = ImageStat.Stat(sample)
            channel_spread = pstdev(stat.stddev)
            return max(stat.stddev) < 2 and channel_spread < 1
    except Exception:
        return False
