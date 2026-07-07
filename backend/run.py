"""Convenience launcher: `python run.py` starts uvicorn with the right config.

From `backend/`:
    pip install -r requirements.txt
    python run.py
"""
from __future__ import annotations

import uvicorn

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    print("=" * 60)
    print("  Genie backend starting")
    print(f"  Local:  http://{settings.host}:{settings.port}")
    print(f"  PIN:    {settings.effective_pin}   (share this with your phone)")
    print("=" * 60)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
