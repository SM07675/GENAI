"""Media Agent — music/video playback and discovery.

Wraps existing YouTube and YouTube Music tools.
"""
from __future__ import annotations
from typing import Any
from .base_agent import BaseAgent
from ..runtime.schemas import Observation, PlanStep, StepResult, TaskContext


class MediaAgent(BaseAgent):
    name = "media"
    description = "Music and video playback, media discovery, YouTube"
    capabilities = [
        "music_play", "video_play", "media_search", "youtube",
        "music_control", "playlist",
    ]
    tools = [
        "play_youtube", "play_youtube_music", "search_youtube_music",
        "play_youtube_playlist", "get_yt_music_recommendations",
    ]

    async def execute(self, step: PlanStep, context: TaskContext) -> StepResult:
        observations: list[Observation] = []
        desc = (step.description or step.title).lower()

        if any(w in desc for w in ["play", "listen", "music", "song"]):
            query = step.description or context.goal.raw_input or step.title
            # Try YouTube Music first, then YouTube
            for tool in ["play_youtube_music", "play_youtube"]:
                try:
                    result, obs = await self._execute_tool(tool, {"query": query}, context)
                    observations.append(obs)
                    if result.status in ("ok", "success"):
                        return StepResult(
                            success=True,
                            message=result.message,
                            data={"tool": tool, "result": result.data or {}},
                            observations=observations,
                            needs_verification=False,
                        )
                except Exception:
                    continue

        elif any(w in desc for w in ["search", "find"]):
            query = step.description or step.title
            try:
                result, obs = await self._execute_tool(
                    "search_youtube_music", {"query": query}, context,
                )
                observations.append(obs)
                return StepResult(
                    success=result.status in ("ok", "success"),
                    message=result.message,
                    data=result.data or {},
                    observations=observations,
                    needs_verification=False,
                )
            except Exception as exc:
                return StepResult(success=False, message=f"Media search failed: {exc}")

        return StepResult(
            success=False,
            message=f"Could not determine media action for: {step.title}",
            observations=observations,
        )
