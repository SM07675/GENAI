"""Offline GGUF LLM fallback for cloud LLM quota/rate-limit failures.

Provides a proper user experience when the configured cloud model is unavailable:
- Loads TinyLlama or any GGUF model from data/models/
- Uses a tailored system prompt to handle common requests gracefully
- For tool-requiring requests (play music, open app) it tells the user
  to retry in a moment when the cloud model is back online
- Stays in character as Genie even in offline mode
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)

_MIN_GGUF_BYTES = 100 * 1024 * 1024
_DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[3] / "data" / "models"

# Compact offline system prompt — stays in Genie character, handles gracefully
_OFFLINE_SYSTEM_PROMPT = """You are Genie, a helpful AI assistant running in offline mode because the main cloud AI provider is temporarily unavailable or rate-limited.

In offline mode:
- You CAN answer questions, have conversations, help with writing, math, and general knowledge
- You CANNOT execute tools like playing music, opening apps, searching the web, or controlling the computer
- When asked to do something that requires tools, be honest and friendly: say you're in offline mode and suggest trying again in a moment

Keep responses SHORT (2-4 sentences max). Be warm, helpful, and stay in character as Genie.
Never say you're "TinyLlama" or mention your model name. You are Genie.
Do NOT use markdown formatting - respond in plain conversational text."""

# Detect tool-intent keywords so we can respond helpfully without breaking
_TOOL_INTENT_KEYWORDS = [
    "play", "open", "launch", "start", "search", "find", "look up",
    "google", "youtube", "spotify", "music", "app", "game", "steam",
    "epic", "xbox", "browser", "chrome", "news", "weather", "timer",
    "alarm", "screenshot", "camera", "type", "click", "scroll",
]


class LocalLLM:
    """Lazy llama.cpp wrapper for offline fallback.

    Provides a real conversational response using a local GGUF model.
    Tool calls are handled gracefully with user-friendly offline messages.
    """

    def __init__(self) -> None:
        self._llm: Any | None = None
        self._model_path: Path | None = None
        self._load_error: str = ""

    def is_enabled(self, settings: Settings | None = None) -> bool:
        settings = settings or get_settings()
        return bool(settings.local_llm_enabled)

    def is_available(self, settings: Settings | None = None) -> bool:
        if not self.is_enabled(settings):
            return False
        try:
            self._resolve_model_path(settings or get_settings())
            self._import_llama(settings or get_settings())
            return True
        except Exception as exc:  # noqa: BLE001
            self._load_error = str(exc)
            return False

    @property
    def load_error(self) -> str:
        return self._load_error

    def generate_from_messages(
        self,
        messages: list[dict],
        *,
        settings: Settings | None = None,
        tools: list[dict] | None = None,
    ) -> dict[str, Any]:
        settings = settings or get_settings()
        if not settings.local_llm_enabled:
            raise RuntimeError("Offline LLM fallback is disabled.")

        llm = self._load(settings)
        local_messages = self._compact_messages(messages)

        # Check if user is asking for something tool-dependent
        user_text = self._get_last_user_text(messages)
        if tools and self._is_tool_request(user_text):
            # Respond helpfully without trying to call tools
            return {
                "role": "assistant",
                "content": (
                    "I'm currently in offline mode because my cloud AI is temporarily "
                    "rate-limited. I can't execute that action right now, but I'll be "
                    "back to full power in just a moment! Please try again in about 10 "
                    "seconds."
                ),
                "tool_calls": None,
            }

        # Generate a real conversational response
        response = llm.create_chat_completion(
            messages=local_messages,
            temperature=settings.local_llm_temperature,
            top_p=settings.local_llm_top_p,
            max_tokens=min(settings.local_llm_max_tokens, 256),  # keep offline replies short
            stop=["</s>", "<|end|>", "<|endoftext|>", "User:", "Human:", "<|user|>"],
            repeat_penalty=1.1,
        )
        msg = response["choices"][0]["message"]
        # Ensure tool_calls is always set (even None) for consistent downstream handling
        msg.setdefault("tool_calls", None)
        return msg

    def _load(self, settings: Settings):
        if self._llm is not None:
            return self._llm
        llama_cls = self._import_llama(settings)
        model_path = self._resolve_model_path(settings)
        logger.info("Loading offline GGUF model: %s", model_path)
        n_threads = max(2, (os.cpu_count() or 4))
        self._llm = llama_cls(
            model_path=str(model_path),
            n_ctx=settings.local_llm_n_ctx,
            n_threads=n_threads,
            n_gpu_layers=settings.local_llm_n_gpu_layers,
            use_mmap=True,
            use_mlock=False,
            verbose=False,
        )
        self._model_path = model_path
        logger.info("Offline model loaded on %d threads", n_threads)
        return self._llm

    def _import_llama(self, settings: Settings):
        try:
            from llama_cpp import Llama
            return Llama
        except ImportError:
            legacy = Path(settings.local_llm_legacy_site_packages or "")
            if legacy.is_dir() and str(legacy) not in sys.path:
                llama_lib = legacy / "llama_cpp" / "lib"
                if sys.platform == "win32" and llama_lib.is_dir():
                    try:
                        os.add_dll_directory(str(llama_lib))
                    except (OSError, AttributeError):
                        pass
                    os.environ["PATH"] = str(llama_lib) + os.pathsep + os.environ.get("PATH", "")

                nvidia_dir = legacy / "nvidia"
                if sys.platform == "win32" and nvidia_dir.is_dir():
                    for subdir in ["cuda_runtime/bin", "cublas/bin"]:
                        bin_path = nvidia_dir / subdir.replace("/", os.sep)
                        if bin_path.is_dir():
                            os.environ["PATH"] = str(bin_path) + os.pathsep + os.environ["PATH"]
                            try:
                                os.add_dll_directory(str(bin_path))
                            except (OSError, AttributeError):
                                pass

                sys.path.append(str(legacy))
            try:
                from llama_cpp import Llama
                logger.info("Using llama_cpp from legacy site-packages: %s", legacy)
                return Llama
            except ImportError as exc:
                raise ImportError(
                    "llama-cpp-python is not installed. Run: "
                    "pip install llama-cpp-python --prefer-binary"
                ) from exc

    def _resolve_model_path(self, settings: Settings) -> Path:
        explicit = Path(settings.local_llm_model_path) if settings.local_llm_model_path else None
        candidates: list[Path] = []
        if explicit:
            candidates.append(explicit)
        candidates.extend(sorted(_DEFAULT_MODEL_DIR.glob("*.gguf")))

        for path in candidates:
            if self._valid_gguf(path):
                return path
        raise FileNotFoundError(
            f"No valid GGUF model found. Put a .gguf file in {_DEFAULT_MODEL_DIR} "
            "or set LOCAL_LLM_MODEL_PATH. "
            "Run: python download_model.py"
        )

    @staticmethod
    def _valid_gguf(path: Path) -> bool:
        if not path.is_file() or path.stat().st_size < _MIN_GGUF_BYTES:
            return False
        try:
            with path.open("rb") as f:
                return f.read(4) == b"GGUF"
        except OSError:
            return False

    @staticmethod
    def _get_last_user_text(messages: list[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content") or ""
                if isinstance(content, list):
                    # Multi-modal content — extract text parts
                    return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
                return str(content)
        return ""

    @staticmethod
    def _is_tool_request(text: str) -> bool:
        """Detect if the user's message requires a tool to fulfil."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in _TOOL_INTENT_KEYWORDS)

    @staticmethod
    def _compact_messages(messages: list[dict]) -> list[dict]:
        """Build compact message list with offline system prompt."""
        # Keep last 6 user/assistant turns (no tool messages — local model can't use them)
        compact: list[dict] = []
        for msg in messages[-12:]:
            role = msg.get("role")
            if role in ("user", "assistant"):
                content = msg.get("content")
                if content:
                    compact.append({"role": role, "content": str(content)})

        return [{"role": "system", "content": _OFFLINE_SYSTEM_PROMPT}] + compact[-8:]


local_llm = LocalLLM()
