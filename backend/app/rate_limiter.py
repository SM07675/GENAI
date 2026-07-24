"""Rate limiting for cloud LLM API requests — NO response caching.

Root cause of the cache-hit loop that was logged:
  _make_cache_key used only the last 2 messages.  Within a single ReAct turn
  the orchestrator calls stream_chat() multiple times (once per tool iteration).
  Each subsequent call had the same last-2-messages hash as the first call, so
  every iteration after the first returned the cached first-iteration response.
  The model appeared to give the same answer repeatedly and tool calls after
  the first were silently skipped.

Decision: remove response caching entirely.
  - LLM responses are non-deterministic and context-dependent.  Caching them
    correctly requires hashing the entire message list, which is expensive and
    still wrong for multi-step ReAct loops.
  - The only safe cache hit is an *exact* repeat of the full conversation — a
    rare event that doesn't justify the complexity or the bugs.
  - Rate limiting (RPM tracking + wait) is preserved: that part works correctly
    and is genuinely needed for quota-limited cloud model tiers.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

log = logging.getLogger("genie.rate_limiter")


class RateLimiter:
    """Token-bucket rate limiter for cloud LLM API requests."""

    def __init__(self, max_requests_per_minute: int = 15):
        self.max_rpm = max_requests_per_minute
        self.request_times: deque[float] = deque()
        self.request_lock = asyncio.Lock()
        log.info("Rate limiter initialised: %d RPM (caching disabled)", max_requests_per_minute)

    async def wait_if_needed(self) -> None:
        """Block until we are under the RPM limit."""
        async with self.request_lock:
            now = time.time()

            # Evict timestamps older than 60 s
            while self.request_times and now - self.request_times[0] > 60:
                self.request_times.popleft()

            if len(self.request_times) >= self.max_rpm:
                oldest    = self.request_times[0]
                wait_time = 60.0 - (now - oldest) + 0.1
                if wait_time > 0:
                    log.warning("Rate limit reached — waiting %.1fs", wait_time)
                    await asyncio.sleep(wait_time)
                    now = time.time()
                    while self.request_times and now - self.request_times[0] > 60:
                        self.request_times.popleft()

            self.request_times.append(time.time())

    # ── stubs kept so callers that reference get_cached / set_cache don't break ──

    def get_cached(self, messages, tools=None):   # noqa: ANN001
        return None   # caching removed — always miss

    def set_cache(self, messages, tools, response):  # noqa: ANN001
        pass          # no-op

    def clear_cache(self) -> None:
        pass

    def get_stats(self) -> dict:
        now = time.time()
        recent = sum(1 for ts in self.request_times if now - ts < 60)
        return {
            "requests_last_minute": recent,
            "max_rpm":              self.max_rpm,
            "utilization":          f"{recent / self.max_rpm * 100:.0f}%",
        }


_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        from .config import get_settings
        settings = get_settings()
        _rate_limiter = RateLimiter(max_requests_per_minute=settings.openrouter_rpm)
    return _rate_limiter
