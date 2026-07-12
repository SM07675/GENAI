"""YouTube Music REST API endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..auth import verify_pin
from ..config import get_settings
from ..services.music_service import music_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/music", tags=["music"])


class AuthSetupRequest(BaseModel):
    headers_raw: str
    pin: str


@router.get("/status")
async def music_status() -> dict:
    return {
        "status": "ok",
        "ytmusicapi_available": music_service.available(),
        "ytmusic_auth_configured": music_service.configured_auth(),
    }


@router.get("/search")
async def search_music(
    q: str = Query(..., description="Search query string"),
    filter: Optional[str] = Query(
        None,
        description="songs | videos | albums | artists | playlists",
    ),
    limit: int = Query(20, ge=1, le=50),
) -> dict:
    try:
        results = music_service.search(query=q, filter=filter, limit=limit)
        return {"status": "ok", "query": q, "filter": filter, "count": len(results), "results": results}
    except Exception as exc:  # noqa: BLE001
        logger.error("music/search failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/song/{video_id}")
async def get_song(video_id: str) -> dict:
    try:
        return {"status": "ok", "data": music_service.get_song(video_id)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/watch/{video_id}")
async def get_watch_playlist(video_id: str, limit: int = Query(25, ge=1, le=50)) -> dict:
    try:
        return {"status": "ok", "data": music_service.get_watch_playlist(video_id=video_id, limit=limit)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/artist/{channel_id}")
async def get_artist(channel_id: str) -> dict:
    try:
        return {"status": "ok", "data": music_service.get_artist(channel_id)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/album/{browse_id}")
async def get_album(browse_id: str) -> dict:
    try:
        return {"status": "ok", "data": music_service.get_album(browse_id)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/lyrics/{browse_id}")
async def get_lyrics(browse_id: str) -> dict:
    try:
        return {"status": "ok", "data": music_service.get_lyrics(browse_id)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/charts")
async def get_charts(country: str = Query("ZZ", description="'ZZ' means global.")) -> dict:
    try:
        return {"status": "ok", "country": country, "data": music_service.get_charts(country=country)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/home")
async def get_home(limit: int = Query(3, ge=1, le=10)) -> dict:
    try:
        data = music_service.get_home(limit=limit)
        return {"status": "ok", "shelves": len(data), "data": data}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/setup-auth")
async def setup_auth(req: AuthSetupRequest) -> dict:
    """Configure authenticated YTMusic headers. PIN required."""
    if not verify_pin(str(req.pin or ""), get_settings()):
        raise HTTPException(status_code=403, detail="Invalid PIN.")
    result = music_service.setup_auth(req.headers_raw)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "Auth setup failed."))
    return result
