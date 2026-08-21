# Adding Tools to Genie

Tools in Genie are registered using the `@tool` decorator in `backend/app/tools/registry.py`.

## Step 1: Define the Tool Function

In an existing tool module or a new file in `backend/app/tools/`:

```python
from ..schemas import ToolResult
from ..os.permissions import SideEffectLevel
from .registry import tool

@tool(
    name="my_custom_tool",
    description="Performs an action on the local environment.",
    side_effect_level=SideEffectLevel.LOCAL_CHANGE,
    category="system",
)
def my_custom_tool(target_path: str, count: int = 1) -> ToolResult:
    """Detailed docstring used for JSON schema parameter extraction."""
    try:
        # Perform action
        return ToolResult(
            status="ok",
            message=f"Processed {count} items at {target_path}",
            data={"count": count, "path": target_path},
        )
    except Exception as exc:
        return ToolResult(
            status="error",
            message=f"Failed: {exc}",
        )
```

## Side Effect Levels

- `SideEffectLevel.READ_ONLY`: Safe read-only data lookup.
- `SideEffectLevel.LOCAL_CHANGE`: Modifies local files/settings.
- `SideEffectLevel.EXTERNAL_NETWORK`: Sends network requests to external APIs.
- `SideEffectLevel.PERSONAL_DATA`: Accesses sensitive user information.
- `SideEffectLevel.DESTRUCTIVE`: Deletes files or terminates processes (requires confirmation in Balanced mode).
- `SideEffectLevel.ACCOUNT`: Modifies account settings or credentials.
