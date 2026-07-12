"""External API status and lightweight REST helpers."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..services.api_manager import api_manager
from ..tools.internet import get_news, search_web

router = APIRouter(prefix="/apis", tags=["apis"])


@router.get("/status")
async def api_status(provider: str = "all") -> dict:
    status = api_manager.status()
    key = provider.strip().lower()
    if key != "all":
        status = {key: status.get(key, {"configured": False, "last_status": "unknown"})}
    return {"status": "ok", "providers": status}


@router.get("/search")
async def api_search(q: str = Query(...), max_results: int = Query(5, ge=1, le=10)) -> dict:
    result = search_web(q, max_results=max_results)
    return result.model_dump()


@router.get("/news")
async def api_news(
    topic: str = "latest",
    max_results: int = Query(5, ge=1, le=20),
    category: str = "",
    country: str = "",
    language: str = "",
    provider: str = "auto",
) -> dict:
    result = get_news(
        topic=topic,
        max_results=max_results,
        category=category,
        country=country,
        language=language,
        provider=provider,
    )
    return result.model_dump()
