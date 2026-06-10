"""Resolve finalized image assets for the card layout layer."""
from __future__ import annotations

import os

from asset_store import get_assets, list_variants


CARD_SPEC_VERSION = "v2"

CARD_ASSET_SLOTS = {
    "v1": {
        1: ["logo"],
        2: ["office", "website_screenshot"],
        3: ["timeline"],
        4: ["product_main"],
        5: ["products_other"],
        6: ["flywheel"],
        7: ["competitors", "competitors_logo_strip", "chart_competitive",
            "chart_ecosystem"],
    },
    "v2": {
        1: ["logo"],
        2: ["website_screenshot"],
        3: ["chart_ecosystem", "product_main"],
        4: ["founder_photo"],
        5: [],
        6: ["flywheel"],
        7: ["competitors", "competitors_logo_strip", "chart_competitive"],
    },
}

CHART_ASSET_KEYS = {"flywheel", "chart_competitive", "chart_ecosystem"}


def resolve_company_assets(db_path: str, company_name: str,
                           spec_version: str = "v1") -> dict:
    """Return card-keyed, layout-ready assets for one company."""
    assets = get_assets(db_path, company_name)
    slots = CARD_ASSET_SLOTS.get(spec_version, CARD_ASSET_SLOTS["v1"])
    card_assets = {}
    for card_index, asset_keys in slots.items():
        card_key = f"card_{card_index}"
        card_assets[card_key] = {}
        for asset_key in asset_keys:
            card_assets[card_key][asset_key] = _resolve_asset(
                db_path,
                company_name,
                asset_key,
                assets.get(asset_key) or {"asset_key": asset_key, "card_index": card_index},
            )

    return {
        "company_name": company_name,
        "card_spec_version": CARD_SPEC_VERSION,
        "card_assets": card_assets,
    }


def _resolve_asset(db_path: str, company_name: str, asset_key: str, asset: dict) -> dict:
    variants = list_variants(db_path, company_name, asset_key)
    selected_variant_id = asset.get("selected_variant_id")
    selected = None
    if selected_variant_id:
        selected = next((v for v in variants if v.get("id") == selected_variant_id), None)
    if not selected:
        selected = next((v for v in variants if v.get("is_selected")), None)
    if selected:
        return _variant_payload(asset_key, selected, status="selected", card_index=asset.get("card_index"))

    scored = [
        v for v in variants
        if v.get("local_path") and not (v.get("reject_reason") or "").strip()
    ]
    if scored:
        best = sorted(scored, key=lambda v: (v.get("final_score") or 0, v.get("created_at") or ""), reverse=True)[0]
        return _variant_payload(asset_key, best, status="fallback", card_index=asset.get("card_index"))

    if asset.get("local_path"):
        return _asset_payload(asset_key, asset)

    return _placeholder_payload(asset_key, asset)


def _variant_payload(asset_key: str, variant: dict, status: str, card_index=None) -> dict:
    url = variant.get("local_path") or ""
    return {
        "asset_key": asset_key,
        "url": url,
        "local_path": url,
        "kind": _asset_kind(asset_key),
        "variant_type": _variant_type(asset_key, variant),
        "format": _format_from_path(url),
        "scale": 1,
        "width": variant.get("width"),
        "height": variant.get("height"),
        "status": status,
        "variant_id": variant.get("id"),
        "selected_variant_id": variant.get("id") if status == "selected" else None,
        "source_type": variant.get("source_type") or "",
        "source_url": variant.get("source_url") or "",
        "final_score": variant.get("final_score") or 0,
        "card_index": card_index,
        "fail_reason": "",
    }


def _asset_payload(asset_key: str, asset: dict) -> dict:
    url = asset.get("local_path") or ""
    return {
        "asset_key": asset_key,
        "url": url,
        "local_path": url,
        "kind": _asset_kind(asset_key),
        "variant_type": _variant_type(asset_key, asset),
        "format": _format_from_path(url),
        "scale": 1,
        "width": None,
        "height": None,
        "status": "selected" if asset.get("status") == "ready" else asset.get("status", "fallback"),
        "variant_id": asset.get("selected_variant_id"),
        "selected_variant_id": asset.get("selected_variant_id"),
        "source_type": asset.get("source_type") or "",
        "source_url": asset.get("source_url") or "",
        "final_score": asset.get("final_score") or 0,
        "card_index": asset.get("card_index"),
        "fail_reason": asset.get("fail_reason") or "",
    }


def _placeholder_payload(asset_key: str, asset: dict) -> dict:
    return {
        "asset_key": asset_key,
        "url": "",
        "local_path": "",
        "kind": _asset_kind(asset_key),
        "variant_type": "placeholder",
        "format": "",
        "scale": 1,
        "width": None,
        "height": None,
        "status": "placeholder",
        "variant_id": None,
        "selected_variant_id": None,
        "source_type": "",
        "source_url": "",
        "final_score": 0,
        "card_index": asset.get("card_index"),
        "fail_reason": asset.get("fail_reason") or "",
    }


def _asset_kind(asset_key: str) -> str:
    return "chart" if asset_key in CHART_ASSET_KEYS else "image"


def _variant_type(asset_key: str, item: dict) -> str:
    if asset_key in CHART_ASSET_KEYS:
        return "svg" if _format_from_path(item.get("local_path") or "") == "svg" else "poster"
    width = item.get("width")
    height = item.get("height")
    if width and height:
        ratio = width / height
        if abs(ratio - 1) < 0.08:
            return "square"
        if abs(ratio - (16 / 9)) < 0.12:
            return "ratio_16_9"
        if abs(ratio - (4 / 3)) < 0.12:
            return "ratio_4_3"
    if asset_key == "logo":
        return "square"
    return "display"


def _format_from_path(path: str) -> str:
    ext = os.path.splitext(path or "")[1].lower().lstrip(".")
    return "jpeg" if ext == "jpg" else ext
