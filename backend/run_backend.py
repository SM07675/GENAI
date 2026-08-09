"""Standalone entrypoint launcher for PyInstaller backend executable.

Avoids relative import issues when app/main.py is run directly.
"""
import sys
import os
import uvicorn

# Ensure the backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app

if __name__ == "__main__":
    port = 8765
    if "--port" in sys.argv:
        try:
            idx = sys.argv.index("--port")
            port = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            pass

    uvicorn.run(app, host="127.0.0.1", port=port)
