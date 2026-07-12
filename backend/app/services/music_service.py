"""Optional YouTube Music metadata service.

The old Genie project used `ytmusicapi` for rich YouTube Music metadata. This
service keeps that capability optional: if the package is not installed, tools
and routes can fall back to official YouTube Data API or browser search.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AUTH_FILE = Path(__file__).resolve().parents[2] / "data" / "ytmusic_auth.json"


class MusicService:
    """Lazy wrapper around ytmusicapi.YTMusic."""

    def __init__(self) -> None:
        self._ytm: Any | None = None
        self._ytm_auth: Any | None = None

    def available(self) -> bool:
        try:
            import ytmusicapi  # noqa: F401
            return True
        except ImportError:
            return False

    def configured_auth(self) -> bool:
        return AUTH_FILE.exists()

    def _client(self) -> Any:
        if self._ytm_auth is not None:
            return self._ytm_auth

        try:
            from ytmusicapi import YTMusic
        except ImportError as exc:
            raise RuntimeError("ytmusicapi is not installed.") from exc

        if AUTH_FILE.exists() and self._ytm_auth is None:
            try:
                self._ytm_auth = YTMusic(str(AUTH_FILE))
                return self._ytm_auth
            except Exception as exc:  # noqa: BLE001
                logger.warning("YTMusic auth file could not be loaded: %s", exc)

        if self._ytm is None:
            self._ytm = YTMusic()
        return self._ytm

    def setup_auth(self, headers_raw: str) -> dict[str, str]:
        """Configure an authenticated YTMusic session from copied request headers."""
        if not headers_raw.strip():
            return {"status": "error", "message": "No headers provided."}
        try:
            from ytmusicapi import YTMusic

            AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
            YTMusic.setup(filepath=str(AUTH_FILE), headers_raw=headers_raw)
            self._ytm_auth = YTMusic(str(AUTH_FILE))
            return {"status": "ok", "message": "YouTube Music authentication configured."}
        except Exception as exc:  # noqa: BLE001
            logger.error("YTMusic auth setup failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def search(self, query: str, filter: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        yt = self._client()
        results = yt.search(query, filter=filter, limit=limit)
        return self._normalize_search(results, filter)

    def get_song(self, video_id: str) -> dict[str, Any]:
        return self._client().get_song(video_id)

    def get_watch_playlist(self, video_id: str, limit: int = 25) -> dict[str, Any]:
        return self._client().get_watch_playlist(videoId=video_id, limit=limit)

    def get_artist(self, channel_id: str) -> dict[str, Any]:
        return self._client().get_artist(channel_id)

    def get_album(self, browse_id: str) -> dict[str, Any]:
        return self._client().get_album(browse_id)

    def get_lyrics(self, browse_id: str) -> dict[str, Any]:
        return self._client().get_lyrics(browse_id)

    def get_charts(self, country: str = "ZZ") -> dict[str, Any]:
        return self._client().get_charts(country=country)

    def get_home(self, limit: int = 3) -> list[dict[str, Any]]:
        return self._client().get_home(limit=limit)

    @staticmethod
    def _normalize_search(raw: list[dict[str, Any]], filter: str | None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in raw:
            result_type = item.get("resultType", filter or "unknown")
            normalized: dict[str, Any] = {
                "resultType": result_type,
                "title": item.get("title", "Unknown"),
                "browseId": item.get("browseId"),
                "videoId": item.get("videoId"),
                "thumbnail": MusicService._pick_thumb(item),
            }

            if result_type in {"song", "video"}:
                normalized["artists"] = [
                    {"name": a.get("name", ""), "id": a.get("id")}
                    for a in (item.get("artists") or [])
                ]
                normalized["album"] = (item.get("album") or {}).get("name")
                normalized["duration"] = item.get("duration")
                normalized["year"] = item.get("year")
                if item.get("videoId"):
                    normalized["url"] = f"https://music.youtube.com/watch?v={item['videoId']}"
            elif result_type == "album":
                normalized["artists"] = [
                    {"name": a.get("name", ""), "id": a.get("id")}
                    for a in (item.get("artists") or [])
                ]
                normalized["year"] = item.get("year")
                normalized["trackCount"] = item.get("trackCount")
            elif result_type == "artist":
                normalized["subscribers"] = item.get("subscribers")
            elif result_type == "playlist":
                normalized["itemCount"] = item.get("itemCount")
                normalized["author"] = item.get("author")

            out.append(normalized)
        return out

    @staticmethod
    def _pick_thumb(item: dict[str, Any]) -> str | None:
        thumbnails = item.get("thumbnails") or []
        if not thumbnails:
            return None
        best = max(
            thumbnails,
            key=lambda t: t.get("width", 0) * t.get("height", 0),
            default=thumbnails[0],
        )
        return best.get("url")


music_service = MusicService()
