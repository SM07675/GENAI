# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for packaging Genie FastAPI Backend executable (backend.exe).

Per spec §17:
- Packages backend into a single self-contained sidecar executable.
- Collects hidden imports for faster-whisper, mss, pywin32, uvicorn, litellm, etc.
- Bundles prompts and runtime assets into _internal resources.
"""
import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

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
]

# Add submodules for complex AI packages
hidden_imports += collect_submodules("app")
hidden_imports += collect_submodules("litellm")

datas = [
    ("app/prompts", "app/prompts"),
]

a = Analysis(
    ["run_backend.py"],
    pathex=["."],
    binaries=[],
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
