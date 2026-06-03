"""Rule-based image candidate scoring."""
from __future__ import annotations

from image_candidate import ImageCandidate


SOURCE_SCORE = {
    "official_og_image": 95,
    "official_screenshot": 90,
    "product_hunt": 85,
    "clearbit_logo": 80,
    "clearbit": 80,
    "google_street_view": 75,
    "street_view": 75,
    "osm_map": 72,
    "screenshot_api": 70,
    "playwright": 65,
    "screenshot_playwright": 65,
    "web_unsplash": 55,
    "unsplash": 55,
    "web_pexels": 55,
    "pexels": 55,
    "web_tavily": 45,
    "tavily": 45,
    "api_generate": 40,
    "ai_generate": 40,
    "import_upload": 100,
    "manual_upload": 100,
    "import_url": 70,
    "svg_render": 75,
}


def score_quality(width: int | None, height: int | None, file_size: int | None) -> float:
    width = width or 0
    height = height or 0
    file_size = file_size or 0
    score = 0

    if width >= 1200:
        score += 30
    elif width >= 800:
        score += 22
    elif width >= 300:
        score += 12

    if height >= 630:
        score += 30
    elif height >= 400:
        score += 20
    elif height >= 200:
        score += 10

    if 50 * 1024 <= file_size <= 4 * 1024 * 1024:
        score += 25
    elif file_size:
        score += 10

    return min(score, 100)


def score_relevance(candidate: ImageCandidate, product_names: list[str] | None = None,
                    competitor_names: list[str] | None = None) -> float:
    haystack = " ".join([
        candidate.image_url or "",
        candidate.source_page or "",
        candidate.title or "",
        candidate.alt_text or "",
        candidate.prompt if hasattr(candidate, "prompt") else "",
    ]).lower()
    score = 0
    company = (candidate.company_name or "").lower()
    if company and company in haystack:
        score += 30
    for product in product_names or []:
        product_l = str(product or "").lower()
        if product_l and product_l in haystack:
            score += 25
            break
    if any(word in haystack for word in ["app", "dashboard", "demo", "screenshot", "interface", "product"]):
        score += 20
    for competitor in competitor_names or []:
        comp_l = str(competitor or "").lower()
        if comp_l and comp_l in haystack:
            score += 20
            break
    if "logo" in haystack:
        score += 15
    if any(word in haystack for word in ["office", "headquarters", "location", "address", "street view"]):
        score += 15
    return min(score, 100)


def score_layout(candidate: ImageCandidate) -> float:
    if not candidate.width or not candidate.height:
        return 0
    ratio = candidate.width / candidate.height
    if 1.2 <= ratio <= 2.2:
        return 90
    if 0.75 <= ratio < 1.2 or 2.2 < ratio <= 3.0:
        return 65
    return 30


def score_candidate(candidate: ImageCandidate, product_names: list[str] | None = None,
                    competitor_names: list[str] | None = None) -> ImageCandidate:
    candidate.source_score = SOURCE_SCORE.get(candidate.source_type, 50)
    candidate.quality_score = score_quality(candidate.width, candidate.height, candidate.file_size)
    candidate.relevance_score = score_relevance(candidate, product_names, competitor_names)
    candidate.layout_score = score_layout(candidate)
    candidate.copyright_score = 100 if candidate.source_type in ("import_upload", "manual_upload") else 65
    candidate.freshness_score = 60
    candidate.final_score = round(
        candidate.source_score * 0.30
        + candidate.quality_score * 0.25
        + candidate.relevance_score * 0.25
        + candidate.layout_score * 0.10
        + candidate.copyright_score * 0.05
        + candidate.freshness_score * 0.05,
        2,
    )
    return candidate
