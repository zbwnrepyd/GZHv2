"""Deterministic field candidate extractors."""
from __future__ import annotations

import re


def _snippet(text: str, start: int, width: int = 180) -> str:
    return text[max(0, start - 40):start + width].strip()


def extract_field_candidates(field_key: str, documents: list[dict]) -> list[dict]:
    candidates: list[dict] = []
    for doc in documents:
        text = str(doc.get("text") or doc.get("content") or "")
        lower = text.lower()
        url = doc.get("url") or doc.get("source_url") or ""
        title = doc.get("title") or ""
        if field_key in ("market_size_value", "tam_value"):
            pattern = r"(USD|US\$|\$|EUR|€|GBP|£|CNY|RMB|¥)?\s*([0-9]+(?:\.[0-9]+)?)\s*(billion|bn|million|m|亿|万)?"
            for match in re.finditer(pattern, text, flags=re.I):
                window = lower[max(0, match.start() - 80):match.end() + 80]
                if any(token in window for token in ("market size", "tam", "addressable market", "市场规模")):
                    candidates.append({
                        "field_key": field_key,
                        "raw_value": match.group(0).strip(),
                        "source_url": url,
                        "source_title": title,
                        "evidence_text": _snippet(text, match.start()),
                        "confidence": "medium",
                    })
                    break
        elif field_key in ("market_cagr", "retention_rate"):
            for match in re.finditer(r"([0-9]+(?:\.[0-9]+)?)\s*%", text):
                window = lower[max(0, match.start() - 50):match.end() + 50]
                keyword = "cagr" if field_key == "market_cagr" else "retention"
                if keyword in window:
                    candidates.append({
                        "field_key": field_key,
                        "raw_value": match.group(1),
                        "source_url": url,
                        "source_title": title,
                        "evidence_text": _snippet(text, match.start()),
                        "confidence": "medium",
                    })
                    break
        elif field_key in ("customer_names", "competitors_top3"):
            if any(token in lower for token in ("customers", "clients", "competitors", "alternatives")):
                candidates.append({
                    "field_key": field_key,
                    "raw_value": title or text[:120],
                    "source_url": url,
                    "source_title": title,
                    "evidence_text": text[:240],
                    "confidence": "low",
                })
        elif field_key in ("product_tech_stack", "competitive_position", "differentiated_opportunity"):
            if text:
                candidates.append({
                    "field_key": field_key,
                    "raw_value": text[:500],
                    "source_url": url,
                    "source_title": title,
                    "evidence_text": text[:500],
                    "confidence": "low",
                })
    return candidates
