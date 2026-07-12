"""Offline GGUF LLM fallback for Gemini quota/rate-limit failures."""

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


class LocalLLM:
    """Lazy llama.cpp wrapper.

    This is deliberately simple: it is a fallback for quota/limit errors, not
    a replacement for Gemini tool calling.
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
        local_messages = self._compact_messages(messages, tools)
        kwargs = {
            "messages": local_messages,
            "temperature": settings.local_llm_temperature,
            "top_p": settings.local_llm_top_p,
            "max_tokens": settings.local_llm_max_tokens,
            "stop": ["</s>", "<|end|>", "<|endoftext|>", "User:", "Human:"],
        }
        if tools:
            kwargs["tools"] = tools

        response = llm.create_chat_completion(**kwargs)
        return response["choices"][0]["message"]

    def _load(self, settings: Settings):
        if self._llm is not None:
            return self._llm
        llama_cls = self._import_llama(settings)
        model_path = self._resolve_model_path(settings)
        logger.info("Loading offline GGUF model: %s", model_path)
        self._llm = llama_cls(
            model_path=str(model_path),
            n_ctx=settings.local_llm_n_ctx,
            n_threads=max(1, os.cpu_count() or 4),
            n_gpu_layers=settings.local_llm_n_gpu_layers,
            use_mmap=True,
            use_mlock=False,
            verbose=False,
        )
        self._model_path = model_path
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
                    # Inject into PATH for transitive DLL dependencies
                    os.environ["PATH"] = str(llama_lib) + os.pathsep + os.environ.get("PATH", "")
                
                # Also inject NVIDIA CUDA DLLs if they exist in the legacy env
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

                sys.path.insert(0, str(legacy))
            try:
                from llama_cpp import Llama
                logger.info("Using llama_cpp from legacy site-packages: %s", legacy)
                return Llama
            except ImportError as exc:
                raise ImportError(
                    "llama-cpp-python is not installed. Install it or keep the old "
                    "GenieAI venv available for fallback imports."
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
            "or set LOCAL_LLM_MODEL_PATH."
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
    def _compact_messages(messages: list[dict], tools: list[dict] | None = None) -> list[dict]:
        """Compact message history for local model."""
        system_text = ""
        compact: list[dict] = []
        for msg in messages[-12:]:  # last 12 messages max
            role = msg.get("role")
            
            if role == "system":
                system_text = str(msg.get("content") or "")
            else:
                compact.append(msg)

        system = system_text.strip()
        return [{"role": "system", "content": system}] + compact


local_llm = LocalLLM()
