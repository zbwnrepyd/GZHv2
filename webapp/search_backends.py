"""Search backend adapter layer for non-LLM collection."""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Union


SearchBackend = Callable[[dict], Union[Awaitable[list[dict]], list[dict]]]


async def _call_backend(backend: SearchBackend, query: dict) -> list[dict]:
    result = backend(query)
    if hasattr(result, "__await__"):
        result = await result  # type: ignore[assignment]
    return result if isinstance(result, list) else []


async def run_parallel_search(
    queries: list[dict],
    backends: dict[str, SearchBackend] | None = None,
    max_concurrency: int = 8,
) -> list[dict]:
    """Run query fan-out without LLM involvement.

    Backends are injected in tests/production adapters. Missing backends produce
    auditable skipped rows instead of raising.
    """
    backends = backends or {}
    sem = asyncio.Semaphore(max(1, max_concurrency))

    async def one(query: dict) -> list[dict]:
        backend_name = query.get("backend", "tavily")
        backend = backends.get(backend_name)
        if not backend:
            return [{**query, "status": "skipped", "reason": f"backend_not_configured:{backend_name}"}]
        async with sem:
            try:
                rows = await _call_backend(backend, query)
                return [{**row, "query": query.get("query"), "intent": query.get("intent"), "field_key": query.get("field_key"), "status": "ok"} for row in rows]
            except Exception as exc:
                return [{**query, "status": "error", "error": repr(exc)}]

    nested = await asyncio.gather(*(one(q) for q in queries))
    return [item for group in nested for item in group]
