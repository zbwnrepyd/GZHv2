"""v3 research identity adapter.

This module keeps the deep-research-report-2.md module boundary while reusing
the existing company_identity implementation.
"""
from __future__ import annotations

from company_identity import CompanyIdentity, build_company_identity as _build


def build_company_identity(company_name: str, website_url: str | None = None) -> dict:
    identity: CompanyIdentity = _build(company_name, website_url or "")
    return {
        "input_name": identity.input_name,
        "display_name": identity.display_name,
        "canonical_company": identity.display_name,
        "company_key": identity.company_key,
        "website_url": identity.website_url,
        "website_host": identity.website_host,
        "root_domain": identity.root_domain,
        "aliases": identity.aliases,
    }
