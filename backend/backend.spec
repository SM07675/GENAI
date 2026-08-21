# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for packaging Genie FastAPI Backend executable (backend.exe).

Per spec §17:
- Packages backend into a single self-contained sidecar executable.
- Collects hidden imports for faster-whisper, mss, pywin32, uvicorn, litellm, etc.
- Bundles prompts and runtime assets into _internal resources.
"""
import sys
import os
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

block_cipher = None
base_dir = os.path.abspath(SPECPATH)
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

hidden_imports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "mss",
    "mss.windows",
    "win32gui",
    "win32process",
    "win32api",
    "faster_whisper",
    "edge_tts",
    "litellm",
    "mem0",
    "langgraph",
    "qdrant_client",
    "tavily",
    "duckduckgo_search",
    "ddgs",
    "structlog",
    "pydantic",
    "pydantic_settings",
    "vosk",
    "vosk.vosk_cffi",
]

# Add submodules for complex AI packages
hidden_imports += collect_submodules("app")
hidden_imports += collect_submodules("litellm")

binaries = collect_dynamic_libs("vosk")

datas = [
    (os.path.join(base_dir, "app", "prompts"), "app/prompts"),
    (
        os.path.join(base_dir, "vosk-model-small-en-us-0.15"),
        "vosk-model-small-en-us-0.15",
    ),
]

a = Analysis(
    [os.path.join(base_dir, "run_backend.py")],
    pathex=[base_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to False in production for windowless sidecar
    icon=None,
)
