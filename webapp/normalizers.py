"""Typed candidate normalization."""
from __future__ import annotations

import json
import re


CURRENCY_MAP = {
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "€": "EUR",
    "EUR": "EUR",
    "£": "GBP",
    "GBP": "GBP",
    "¥": "CNY",
    "RMB": "CNY",
    "CNY": "CNY",
}


def _number(raw: str) -> float | None:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", raw or "")
    return float(match.group(1)) if match else None


def _currency(raw: str) -> str:
    upper = (raw or "").upper()
    for token, code in CURRENCY_MAP.items():
        if token.upper() in upper:
            return code
    return ""


def normalize_candidate(field_key: str, candidate: dict) -> dict:
    raw = str(candidate.get("raw_value", "")).strip()
    row = dict(candidate)
    row["field_key"] = field_key
    row["field_value"] = raw
    row["value_type"] = "text"
    row["norm_value"] = ""
    row["currency_code"] = ""
    row["unit"] = ""
    row["source_urls"] = json.dumps([candidate.get("source_url", "")], ensure_ascii=False)

    if field_key.endswith("_value") or field_key in {"market_cagr", "retention_rate", "ltv", "cac", "ltv_cac_ratio", "mau"}:
        num = _number(raw)
        row["value_type"] = "number"
        row["norm_value"] = "" if num is None else str(num)
        row["currency_code"] = _currency(raw)
        if any(unit in raw.lower() for unit in ("billion", "bn")):
            row["unit"] = "billion"
        elif any(unit in raw.lower() for unit in ("million", " m")):
            row["unit"] = "million"
    elif field_key in {"customer_names", "customer_choice_evidence", "competitors_top3", "pricing_tiers"}:
        row["value_type"] = "json"
    return row
