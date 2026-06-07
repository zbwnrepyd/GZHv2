"""公司身份归一化 — 防止 Limitless/limitless 被当成不同公司。

company_key 是系统内部主键（优先取官网域名如 limitless.ai），
display_name 是界面展示名。不再让展示名承担数据库身份职责。
"""
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class CompanyIdentity:
    input_name: str
    display_name: str
    company_key: str
    website_url: str
    website_host: str
    root_domain: str
    aliases: list[str]


def _normalize_host(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.netloc or parsed.path).lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host.strip("/")


def _root_domain(host: str) -> str:
    if not host:
        return ""
    return host.split(".")[0]


def _display_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return ""
    if name.islower():
        return name[:1].upper() + name[1:]
    return name


def build_company_aliases(input_name: str, display_name: str,
                          host: str, root: str) -> list[str]:
    terms: set[str] = set()
    for item in [input_name, display_name, input_name.lower(),
                 display_name.lower(), root, host]:
        item = (item or "").strip()
        if item:
            terms.add(item)

    if display_name and host:
        terms.add(f'"{display_name}" "{host}"')
    if root and host:
        terms.add(f'"{root}" "{host}"')
    if display_name:
        terms.add(f"{display_name} AI")
        terms.add(f"{display_name} startup")
    if root:
        terms.add(f"{root} AI")
        terms.add(f"{root} startup")

    return [t for t in terms if len(t) >= 2]


def build_company_identity(company_name: str,
                           company_url: str = "") -> CompanyIdentity:
    input_name = (company_name or "").strip()
    host = _normalize_host(company_url)
    root = _root_domain(host)
    display = _display_name(input_name or root)
    key = host or input_name.lower()

    aliases = build_company_aliases(
        input_name=input_name, display_name=display,
        host=host, root=root,
    )

    return CompanyIdentity(
        input_name=input_name,
        display_name=display,
        company_key=key,
        website_url=company_url.strip(),
        website_host=host,
        root_domain=root,
        aliases=aliases,
    )
