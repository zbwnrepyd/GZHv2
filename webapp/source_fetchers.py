"""Source fetching and YouTube intelligence helpers."""
from __future__ import annotations

import asyncio
import hashlib
import urllib.request
import urllib.robotparser
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup


GLOBAL_CONCURRENCY = 8
PER_HOST_CONCURRENCY = 2


@dataclass
class FetchContext:
    host_limiters: defaultdict[str, asyncio.Semaphore] = field(
        default_factory=lambda: defaultdict(lambda: asyncio.Semaphore(PER_HOST_CONCURRENCY))
    )
    seen: set[str] = field(default_factory=set)


def norm_url(url: str) -> str:
    parsed = urlparse(url if "://" in str(url) else f"https://{url}")
    return urlunparse((parsed.scheme.lower() or "https", parsed.netloc.lower().replace("www.", ""), parsed.path.rstrip("/"), "", "", ""))


def robots_allowed(url: str, user_agent: str = "GZHv2ResearchBot", robots_txt: str | None = None) -> dict:
    parsed = urlparse(url if "://" in str(url) else f"https://{url}")
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    try:
        if robots_txt is None:
            parser.set_url(robots_url)
            parser.read()
        else:
            parser.parse(robots_txt.splitlines())
        allowed = parser.can_fetch(user_agent, url)
        return {
            "allowed": bool(allowed),
            "robots_status": "allowed" if allowed else "disallowed",
            "robots_url": robots_url,
        }
    except Exception as exc:
        return {
            "allowed": False,
            "robots_status": "robots_error",
            "robots_url": robots_url,
            "error": repr(exc),
        }


async def fetch_text(_client, url: str, ctx: FetchContext) -> dict:
    host = urlparse(url).netloc.lower()
    async with ctx.host_limiters[host]:
        def _read() -> tuple[int, str, str]:
            req = urllib.request.Request(url, headers={"User-Agent": "GZHv2ResearchBot/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read(500_000).decode("utf-8", "ignore")
                return resp.status, resp.headers.get("content-type", ""), body

        status, content_type, html = await asyncio.to_thread(_read)
        return {
            "url": url,
            "norm_url": norm_url(url),
            "status_code": status,
            "content_type": content_type,
            "html": html,
            "sha1": hashlib.sha1(html.encode("utf-8", "ignore")).hexdigest(),
        }


def extract_visible_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(" ").split())


async def fetch_documents(
    search_hits: list[dict],
    fetcher: Callable[[object, str, FetchContext], Awaitable[dict]] = fetch_text,
    max_concurrency: int = GLOBAL_CONCURRENCY,
) -> list[dict]:
    ctx = FetchContext()
    sem = asyncio.Semaphore(max(1, max_concurrency))
    tasks = []
    for hit in search_hits:
        url = (hit.get("url") or hit.get("source_url") or "").strip()
        if not url:
            continue
        key = norm_url(url)
        if key in ctx.seen:
            continue
        ctx.seen.add(key)

        async def one(target: str = url):
            async with sem:
                try:
                    doc = await fetcher(None, target, ctx)
                    return {
                        "status": "ok",
                        "url": doc["url"],
                        "norm_url": doc.get("norm_url") or norm_url(doc["url"]),
                        "sha1": doc.get("sha1", ""),
                        "status_code": doc.get("status_code"),
                        "content_type": doc.get("content_type", ""),
                        "text": extract_visible_text(doc.get("html", "")),
                    }
                except Exception as exc:
                    return {"status": "error", "url": target, "error": repr(exc)}

        tasks.append(one())
    return await asyncio.gather(*tasks) if tasks else []


def _default_metadata_lookup(video_url: str) -> dict:
    return {"video_id": video_url.rsplit("=", 1)[-1] if "=" in video_url else video_url, "url": video_url}


def _default_subtitle_loader(video_url: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        video_id = video_url.rsplit("=", 1)[-1] if "=" in video_url else video_url.rsplit("/", 1)[-1]
        rows = YouTubeTranscriptApi.get_transcript(video_id)
        return "\n".join(row.get("text", "") for row in rows)
    except Exception:
        return ""


def extract_youtube_intel(
    video_url: str,
    metadata_lookup: Callable[[str], dict] | None = None,
    subtitle_loader: Callable[[str], str] | None = None,
    asr_transcriber: Callable[[str], str] | None = None,
    scene_detector: Callable[[str], list] | None = None,
) -> dict:
    attempted: list[str] = []
    metadata_lookup = metadata_lookup or _default_metadata_lookup
    subtitle_loader = subtitle_loader or _default_subtitle_loader
    asr_transcriber = asr_transcriber or (lambda _url: "")
    scene_detector = scene_detector or (lambda _url: [])

    attempted.append("metadata")
    meta = metadata_lookup(video_url) or {}
    attempted.append("public_subtitles")
    transcript = subtitle_loader(video_url) or ""
    status = "public_subtitles" if transcript else "unavailable"
    if not transcript:
        attempted.append("asr")
        transcript = asr_transcriber(video_url) or ""
        status = "asr" if transcript else "unavailable"
    attempted.append("scenes")
    scenes = scene_detector(video_url) or []
    return {
        "meta": meta,
        "transcript": transcript,
        "transcript_status": status,
        "scenes": scenes,
        "timestamp_summary": [],
        "attempted_methods": attempted,
    }
