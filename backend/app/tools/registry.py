"""Tool registry: turn plain Python functions into GLM tool calls.

Usage in any module under `tools/`:

    from .registry import tool, ToolResult

    @tool
    def set_volume(percent: int) -> ToolResult:
        '''Set the master volume to a specific percentage (0-100).'''
        ...
        return ToolResult(status="ok", message="Volume set to 50%")

The decorator introspects the function's signature + docstring to build a
JSON-schema descriptor compatible with GLM 5.2's OpenAI-style tool-calling.
The module `__init__.py` imports every tool module so they self-register.
"""
from __future__ import annotations

import inspect
import typing
from dataclasses import dataclass
from typing import Any, Callable, get_args, get_origin, get_type_hints
from uuid import uuid4

from ..os.permissions import SideEffectLevel, side_effect_from_value
from ..schemas import ToolResult


# --- JSON-schema type mapping -------------------------------------------
_PY_TO_JSONSCHEMA: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def _annotation_to_schema(annotation: Any) -> dict[str, Any]:
    """Convert a Python type annotation to a JSON-schema fragment."""
    if annotation in _PY_TO_JSONSCHEMA:
        return {"type": _PY_TO_JSONSCHEMA[annotation]}

    origin = get_origin(annotation)
    if origin in (list, typing.List):
        inner = get_args(annotation)[0]
        return {"type": "array", "items": _annotation_to_schema(inner)}
    if origin in (dict, typing.Dict):
        return {"type": "object"}
    # Fallback: treat unknowns as strings (model still understands free text).
    return {"type": "string"}


@dataclass
class ToolEntry:
    """A registered tool = executable function + JSON-schema descriptor."""
    name: str
    description: str
    parameters: dict[str, Any]            # JSON schema of the arguments
    func: Callable[..., ToolResult]
    side_effect_level: SideEffectLevel = SideEffectLevel.READ_ONLY
    permissions: tuple[str, ...] = ()
    timeout_ms: int = 30_000
    audit_category: str = "general"
    streaming: bool = False

    def to_schema(self) -> dict[str, Any]:
        """OpenAI/GLM tool descriptor (function-calling format)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_manifest(self) -> dict[str, Any]:
        """Runtime manifest used by Genie OS tool discovery and UI audit panels."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "side_effect_level": self.side_effect_level.value,
            "permissions": list(self.permissions),
            "timeout_ms": self.timeout_ms,
            "audit_category": self.audit_category,
            "streaming": self.streaming,
        }


# Global registry. Tool modules register themselves at import time.
REGISTRY: dict[str, ToolEntry] = {}


def tool(
    func: Callable[..., ToolResult] | None = None,
    *,
    side_effect_level: str | SideEffectLevel | None = None,
    permissions: tuple[str, ...] | list[str] = (),
    timeout_ms: int = 30_000,
    audit_category: str = "general",
    streaming: bool = False,
) -> Callable[..., ToolResult]:
    """Decorator that registers `func` and derives its schema from type hints.

    The function's docstring becomes the tool description; the first line is
    used as a short summary. Parameters are derived from annotations, and any
    parameter with a default value is marked as not required.
    """
    if func is None:
        return lambda wrapped: tool(
            wrapped,
            side_effect_level=side_effect_level,
            permissions=permissions,
            timeout_ms=timeout_ms,
            audit_category=audit_category,
            streaming=streaming,
        )

    name = func.__name__
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func, include_extras=False)
    except Exception:  # noqa: BLE001 - defensive for forward refs
        hints = {p: str for p in sig.parameters}

    properties: dict[str, Any] = {}
    required: list[str] = []
    for pname, param in sig.parameters.items():
        ann = hints.get(pname, str)
        # Optional[X] / X | None -> unwrap and mark non-required.
        is_optional = False
        origin = get_origin(ann)
        if origin is typing.Union:
            args = [a for a in get_args(ann) if a is not type(None)]
            if len(args) == 1:
                ann = args[0]
                is_optional = True
        if param.default is not inspect.Parameter.empty:
            is_optional = True

        schema = _annotation_to_schema(ann)
        # Pull a per-param hint from the docstring if present (Google-style).
        schema["description"] = _param_doc(func.__doc__, pname) or pname
        properties[pname] = schema
        if not is_optional:
            required.append(pname)

    parameters = {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }

    description = (func.__doc__ or name).strip().split("\n", 1)[0]
    REGISTRY[name] = ToolEntry(
        name=name,
        description=description,
        parameters=parameters,
        func=func,
        side_effect_level=side_effect_from_value(side_effect_level) if side_effect_level else _infer_side_effect(name),
        permissions=tuple(permissions),
        timeout_ms=timeout_ms,
        audit_category=audit_category,
        streaming=streaming,
    )
    return func


def _param_doc(docstring: str | None, param: str) -> str | None:
    """Best-effort extraction of a `:param name: desc` line from a docstring."""
    if not docstring:
        return None
    needle = f":param {param}:"
    for line in docstring.splitlines():
        s = line.strip()
        if s.startswith(needle):
            return s[len(needle):].strip()
    return None


def tool_schemas() -> list[dict[str, Any]]:
    """All registered tool schemas, ready to hand to GLM."""
    return [entry.to_schema() for entry in REGISTRY.values()]


def tool_manifests() -> list[dict[str, Any]]:
    """All registered tool manifests with runtime policy metadata."""
    return [entry.to_manifest() for entry in REGISTRY.values()]


def execute_tool(name: str, arguments: dict[str, Any]) -> ToolResult:
    """Dispatch a tool call by name. Returns a ToolResult on any path.

    Synchronous on purpose: tools wrap blocking OS calls, and the orchestrator
    offloads this whole function to a worker thread via `asyncio.to_thread`.
    """
    entry = REGISTRY.get(name)
    if entry is None:
        return ToolResult(
            status="error",
            message=f"Unknown tool '{name}'.",
            data={"available": list(REGISTRY.keys())},
        )

    call_id = f"tool_{uuid4().hex}"
    _emit_tool_started(entry, call_id, arguments)
    try:
        result = entry.func(**arguments)
        if not isinstance(result, ToolResult):
            result = ToolResult(status="ok", message=str(result))
        _emit_tool_completed(entry, call_id, result)
        return result
    except TypeError as e:
        # Bad/missing arguments from the model.
        result = ToolResult(
            status="error",
            message=f"Invalid arguments for '{name}': {e}",
            data={"parameters": entry.parameters},
        )
        _emit_tool_completed(entry, call_id, result)
        return result
    except Exception as e:  # noqa: BLE001 - surface every failure to the model
        result = ToolResult(
            status="error",
            message=f"Tool '{name}' failed: {e.__class__.__name__}: {e}",
        )
        _emit_tool_completed(entry, call_id, result)
        return result


def _infer_side_effect(name: str) -> SideEffectLevel:
    n = name.lower()
    if n.startswith(("search_", "get_", "capture_", "read_", "calculate")):
        return SideEffectLevel.READ_ONLY
    if "news" in n or "weather" in n or "time" in n:
        return SideEffectLevel.READ_ONLY
    if "clipboard_read" in n:
        return SideEffectLevel.PERSONAL_DATA
    if n in {"clipboard_write", "ghost_type", "set_volume", "trigger_night_light"}:
        return SideEffectLevel.LOCAL_CHANGE
    if n.startswith(("open_", "play_")):
        return SideEffectLevel.EXTERNAL_NETWORK if "url" in n or "youtube" in n else SideEffectLevel.LOCAL_CHANGE
    if n.startswith(("close_", "sleep_", "launch_")):
        return SideEffectLevel.LOCAL_CHANGE
    return SideEffectLevel.READ_ONLY


def _emit_tool_started(entry: ToolEntry, call_id: str, arguments: dict[str, Any]) -> None:
    try:
        from ..os import get_kernel

        get_kernel().record_tool_started(
            tool_name=entry.name,
            arguments={"call_id": call_id, **(arguments or {})},
            side_effect_level=entry.side_effect_level,
        )
    except Exception:
        return


def _emit_tool_completed(entry: ToolEntry, call_id: str, result: ToolResult) -> None:
    try:
        from ..os import get_kernel

        get_kernel().record_tool_completed(
            tool_name=entry.name,
            status=result.status,
            message=f"{call_id}: {result.message}",
        )
    except Exception:
        return
