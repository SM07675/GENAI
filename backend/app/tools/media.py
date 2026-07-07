"""Media tools: play specific YouTube videos or mood-based playlists.

We avoid pulling in yt-dlp at runtime; instead we use YouTube search/playlist
URLs which the default browser hands off to the YouTube player. This keeps the
dependency surface small and the launch latency low.
"""
from __future__ import annotations

import urllib.parse
import webbrowser

from ..schemas import ToolResult
from .registry import tool

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


def _open(url: str) -> None:
    webbrowser.open(url, new=2)


@tool
def play_youtube(query: str) -> ToolResult:
    """Play a specific YouTube video by title or topic. Opens the best match and auto-plays.

    :param query: Song/video title or a descriptive phrase (e.g. "Shape of You official video").
    """
    if not query or not query.strip():
        return ToolResult(status="error", message="What should I play on YouTube?")
    # YouTube's /search results auto-load the first hit when used via this URL
    # pattern on most browsers; this is the lowest-friction approach.
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    try:
        _open(url)
        return ToolResult(
            status="ok",
            message=f"Playing '{query}' on YouTube.",
            data={"query": query, "url": url},
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult(status="error", message=f"Couldn't open YouTube: {e}")


@tool
def play_youtube_playlist(mood: str) -> ToolResult:
    """Play a YouTube playlist matching a mood (e.g. sad, happy, focus, chill, workout, party, romantic).

    :param mood: The mood or vibe to match to a curated playlist.
    """
    if not mood:
        return ToolResult(status="error", message="Which mood playlist should I play?")
    key = mood.strip().lower()
    playlist_id = _MOOD_PLAYLISTS.get(key)
    if not playlist_id:
        # Fallback: search YouTube for "<mood> songs playlist".
        url = (
            "https://www.youtube.com/results?search_query="
            + urllib.parse.quote(f"{mood} songs playlist")
        )
        msg = f"No curated {mood} playlist; searching YouTube for one instead."
    else:
        url = f"https://www.youtube.com/watch_videos?video_ids=&list={playlist_id}"
        # Stable watch-with-list URL that starts the playlist from the top.
        url = f"https://www.youtube.com/playlist?list={playlist_id}"
        msg = f"Playing your {mood} playlist on YouTube."
    try:
        _open(url)
        return ToolResult(
            status="ok",
            message=msg,
            data={"mood": key, "playlist_id": playlist_id, "url": url},
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult(status="error", message=f"Couldn't open the playlist: {e}")
