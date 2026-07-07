"""Tool package: importing this module registers every tool.

The `@tool` decorator (see `registry.py`) self-registers each function into
`REGISTRY` at import time. Importing this package therefore makes the full
tool set available. We import with `# noqa: F401` because the side effect
(registration) is the whole point.
"""
from . import apps        # noqa: F401  (registers open_app, close_app, launch_steam_game)
from . import web         # noqa: F401  (open_url, open_whatsapp_chat, open_instagram_chat)
from . import media       # noqa: F401  (play_youtube, play_youtube_playlist)
from . import system_control  # noqa: F401 (set_volume, trigger_night_light, sleep_pc)
from . import ghost_type  # noqa: F401  (ghost_type)
from . import screen_vision  # noqa: F401 (capture_screen)
from . import memory      # noqa: F401 (manage_note)

from .registry import REGISTRY as TOOLS, tool, tool_schemas, execute_tool

# Public list of tool descriptors for GLM (built once at import).
TOOL_SCHEMAS = tool_schemas()

__all__ = ["TOOLS", "TOOL_SCHEMAS", "tool", "tool_schemas", "execute_tool"]
