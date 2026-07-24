"""Media tools: play specific YouTube videos or mood-based playlists.

We avoid pulling in yt-dlp at runtime; instead we use YouTube search/playlist
URLs which the default browser hands off to the YouTube player. This keeps the
dependency surface small and the launch latency low.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
import webbrowser
from typing import Any

from ..schemas import ToolResult
from ..services.api_manager import api_manager
from ..services.music_service import music_service
from .registry import tool

logger = logging.getLogger(__name__)

# Curated mood -> playlist mapping. Swap these IDs for your own playlists.
# Each value is a YouTube playlist ID (the "PL..." string).
_MOOD_PLAYLISTS: dict[str, str] = {
    "sad": "PLcGEUtMSny0ZF5UHo-iSeIcfqB-yzy-Tv",        # sad songs
    "happy": "PLw-VjHDlEOgs658kAHR_LAaILBXb-s6Q5",      # happy hits
    "focus": "PL4oiFCCugq3O5Q6OlQK7hnvMK8XjM4Oy4",      # focus / study
    "chill": "PLRCGXgd3Mnjoc_TdMrl5UTQO84wL4tQHn",      # chill lofi
    "workout": "PLyORnIW1xM6e7Q5yf6Wb0-SXxiHX425VK",    # workout
    "party": "PL0l_L_pxm8AhR4X-Wv8tTnILp8qWNaAy1",      # party
    "romantic": "PL64gKj6iYjkefYHpFn5dGT4dYf9a4Oo7x",   # romantic
}

_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _open(url: str) -> None:
    # Used for fallback web searches, but not for media playing anymore
    webbrowser.open(url, new=2)


def _youtube_music_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search music videos using the official YouTube Data API."""
    key = api_manager.api_key("youtube")
    if not key:
        return []

    settings = api_manager.settings
    data = api_manager.get_json(
        "youtube",
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "key": key,
            "part": "snippet",
            "type": "video",
            "videoCategoryId": "10",  # Music
            "q": query,
            "maxResults": max(1, min(int(max_results), 10)),
            "regionCode": settings.youtube_region_code,
            "safeSearch": "moderate",
        },
    )

    results: list[dict[str, Any]] = []
    for item in data.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not video_id:
            continue
        results.append({
            "title": snippet.get("title", ""),
            "artist_or_channel": snippet.get("channelTitle", ""),
            "video_id": video_id,
            "published_at": snippet.get("publishedAt", ""),
            "url": f"https://music.youtube.com/watch?v={video_id}",
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail": (snippet.get("thumbnails", {}).get("medium") or {}).get("url", ""),
        })
    return results


def _youtube_video_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search general YouTube videos using the official YouTube Data API."""
    key = api_manager.api_key("youtube")
    if not key:
        return []

    settings = api_manager.settings
    data = api_manager.get_json(
        "youtube",
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "key": key,
            "part": "snippet",
            "type": "video",
            "q": query,
            "maxResults": max(1, min(int(max_results), 10)),
            "regionCode": settings.youtube_region_code,
            "safeSearch": "moderate",
        },
    )

    results: list[dict[str, Any]] = []
    for item in data.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not video_id:
            continue
        results.append({
            "title": snippet.get("title", ""),
            "artist_or_channel": snippet.get("channelTitle", ""),
            "video_id": video_id,
            "published_at": snippet.get("publishedAt", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail": (snippet.get("thumbnails", {}).get("medium") or {}).get("url", ""),
            "provider": "youtube_data_api",
        })
    return results


def _youtube_music_search_url(query: str) -> str:
    return "https://music.youtube.com/search?q=" + urllib.parse.quote(query)


def _youtube_search_url(query: str) -> str:
    return "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)


def _ytmusicapi_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    results = music_service.search(query=query, filter="songs", limit=max_results)
    normalized: list[dict[str, Any]] = []
    for item in results:
        video_id = item.get("videoId")
        artists = item.get("artists") or []
        artist_names = ", ".join(a.get("name", "") for a in artists if a.get("name"))
        normalized.append({
            "title": item.get("title", ""),
            "artist_or_channel": artist_names,
            "video_id": video_id,
            "album": item.get("album") or "",
            "duration": item.get("duration") or "",
            "year": item.get("year") or "",
            "url": f"https://music.youtube.com/watch?v={video_id}" if video_id else "",
            "thumbnail": item.get("thumbnail") or "",
            "provider": "ytmusicapi",
        })
    return normalized


def _extract_youtube_video_id(url: str) -> str | None:
    raw = (url or "").strip()
    if not raw:
        return None

    parsed = urllib.parse.urlparse(raw)
    params = urllib.parse.parse_qs(parsed.query)
    if params.get("uddg"):
        return _extract_youtube_video_id(urllib.parse.unquote(params["uddg"][0]))

    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/", 1)[0]
        return candidate if _YOUTUBE_ID_RE.match(candidate) else None

    if host in {"youtube.com", "music.youtube.com", "m.youtube.com"}:
        if params.get("v") and _YOUTUBE_ID_RE.match(params["v"][0]):
            return params["v"][0]
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"embed", "shorts"} and _YOUTUBE_ID_RE.match(parts[1]):
            return parts[1]

    return None


def _ddg_youtube_video_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Find YouTube videos without requiring the YouTube Data API."""
    try:
        from ddgs import DDGS
    except ImportError:
        return []

    results: list[dict[str, Any]] = []
    search_query = f"site:youtube.com/watch {query}"
    try:
        with DDGS() as ddgs:
            for item in ddgs.text(search_query, max_results=max(1, min(int(max_results), 10))):
                url = item.get("href") or item.get("url") or ""
                video_id = _extract_youtube_video_id(url)
                if not video_id:
                    continue
                results.append({
                    "title": item.get("title", ""),
                    "artist_or_channel": item.get("source", ""),
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                    "thumbnail": "",
                    "provider": "duckduckgo_youtube",
                })
                if len(results) >= max_results:
                    break
    except Exception as exc:  # noqa: BLE001
        logger.info("DuckDuckGo YouTube search failed: %s", exc)
    return results


@tool
def play_youtube(query: str) -> ToolResult:
    """Play a specific YouTube video, song, lecture, or topic in the background.

    :param query: What to play (e.g. 'Bohemian Rhapsody', 'Python tutorial', 'IPL highlights').
    """
    if not query or not query.strip():
        return ToolResult(status="error", message="What should I play on YouTube?")
    
    fallback_url = _youtube_search_url(query)

    try:
        results = _youtube_video_search(query, max_results=1)
        if results and results[0].get("video_id"):
            video_id = results[0]["video_id"]
            return ToolResult(
                status="ok",
                message=f"Playing {results[0]['title']} in the background.",
                data={"action": "play_media", "video_id": video_id, "query": query},
            )
        results = _ddg_youtube_video_search(query, max_results=1)
        if results and results[0].get("video_id"):
            first = results[0]
            return ToolResult(
                status="ok",
                message=f"Playing {first.get('title') or query} in the background.",
                data={"action": "play_media", "video_id": first["video_id"], "query": query},
            )

        return ToolResult(
            status="not_found",
            message=f"Couldn't find a playable YouTube result for '{query}'.",
            data={"suggestion": "open_url", "url": fallback_url, "provider": "browser_fallback"},
        )
    except Exception as e:
        return ToolResult(
            status="not_found",
            message=f"YouTube search failed: {e}. Opening browser search instead.",
            data={"suggestion": "open_url", "url": fallback_url, "provider": "browser_fallback"},
        )


@tool
def play_youtube_playlist(mood: str) -> ToolResult:
    """Play a background YouTube playlist matching a mood (e.g. sad, happy, focus, chill, workout, party, romantic).

    :param mood: The mood or vibe to match to a curated playlist.
    """
    if not mood:
        return ToolResult(status="error", message="Which mood playlist should I play?")
    key = mood.strip().lower()
    playlist_id = _MOOD_PLAYLISTS.get(key)
    
    if not playlist_id:
        return ToolResult(
            status="not_found", 
            message=f"No curated playlist for '{mood}'. Try asking for a specific song instead."
        )
    
    return ToolResult(
        status="ok",
        message=f"Playing your {mood} playlist in the background.",
        data={"action": "play_media", "playlist_id": playlist_id, "mood": key},
    )


@tool
def search_youtube_music(query: str, max_results: int = 5) -> ToolResult:
    """Search YouTube Music using YouTube Data API metadata when configured.

    :param query: Song, artist, album, playlist, podcast, or lecture to search.
    :param max_results: Maximum number of music results to return.
    """
    if not query or not query.strip():
        return ToolResult(status="error", message="What should I search on YouTube Music?")

    fallback_url = _youtube_music_search_url(query)
    provider_pref = api_manager.settings.youtube_music_provider.strip().lower()

    if provider_pref in {"auto", "ytmusicapi"} and music_service.available():
        try:
            results = _ytmusicapi_search(query, max_results=max_results)
            if results:
                return ToolResult(
                    status="ok",
                    message=f"Found {len(results)} YouTube Music results for '{query}'.",
                    data={"results": results, "provider": "ytmusicapi"},
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("ytmusicapi search failed: %s", e)

    if provider_pref in {"ytmusicapi"}:
        return ToolResult(
            status="not_found",
            message="ytmusicapi is not available right now. I can still open YouTube Music search.",
            data={"suggestion": "open_url", "url": fallback_url, "provider": "browser_fallback"},
        )

    try:
        if provider_pref != "browser" and api_manager.is_configured("youtube"):
            results = _youtube_music_search(query, max_results=max_results)
            if results:
                return ToolResult(
                    status="ok",
                    message=f"Found {len(results)} YouTube Music results for '{query}'.",
                    data={"results": results, "provider": "youtube_data_api"},
                )

        results = _ddg_youtube_video_search(query, max_results=max_results)
        if results:
            return ToolResult(
                status="ok",
                message=f"Found {len(results)} YouTube results for '{query}'.",
                data={"results": results, "provider": "duckduckgo_youtube"},
            )

        return ToolResult(
            status="not_found",
            message=f"No YouTube Music results found for '{query}'.",
            data={"suggestion": "open_url", "url": fallback_url, "provider": "browser_fallback"},
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult(
            status="not_found",
            message=f"YouTube Music search failed: {e}. Opening browser search instead.",
            data={"suggestion": "open_url", "url": fallback_url, "provider": "browser_fallback"},
        )


@tool
def play_youtube_music(query: str) -> ToolResult:
    """Play a song, artist, album, playlist, podcast, or lecture on YouTube Music in the background.

    :param query: What to play on YouTube Music.
    """
    if not query or not query.strip():
        return ToolResult(status="error", message="What should I play on YouTube Music?")

    try:
        provider_pref = api_manager.settings.youtube_music_provider.strip().lower()

        if provider_pref in {"auto", "ytmusicapi"} and music_service.available():
            results = _ytmusicapi_search(query, max_results=1)
            playable = next((item for item in results if item.get("video_id")), None)
            if playable:
                return ToolResult(
                    status="ok",
                    message=f"Playing {playable['title']} in the background.",
                    data={"action": "play_media", "video_id": playable["video_id"], "query": query},
                )

        if provider_pref not in {"ytmusicapi", "browser"} and api_manager.is_configured("youtube"):
            results = _youtube_music_search(query, max_results=1)
            if results and results[0].get("video_id"):
                first = results[0]
                return ToolResult(
                    status="ok",
                    message=f"Playing {first['title']} in the background.",
                    data={"action": "play_media", "video_id": first["video_id"], "query": query},
                )

        results = _ddg_youtube_video_search(f"{query} song music", max_results=1)
        if results and results[0].get("video_id"):
            first = results[0]
            return ToolResult(
                status="ok",
                message=f"Playing {first.get('title') or query} in the background.",
                data={"action": "play_media", "video_id": first["video_id"], "query": query},
            )

        return ToolResult(
            status="not_found",
            message=f"Could not find any playable results for '{query}'.",
            data={
                "suggestion": "open_url",
                "url": _youtube_music_search_url(query),
                "provider": "browser_fallback",
            },
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult(
            status="not_found",
            message=f"Couldn't play YouTube Music: {e}. Opening browser search instead.",
            data={
                "suggestion": "open_url",
                "url": _youtube_music_search_url(query),
                "provider": "browser_fallback",
            },
        )

@tool
def stop_music() -> ToolResult:
    """Stop the background music player."""
    return ToolResult(
        status="ok",
        message="Music stopped.",
        data={"action": "stop_media"}
    )
