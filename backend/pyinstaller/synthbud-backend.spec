# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the synthbud desktop backend executable.

Produces a single Mach-O binary that embeds CPython, the FastAPI app,
the Alembic migrations, and all runtime pip dependencies. The resulting
binary replaces frontend/src-tauri/bin/synthbud-backend so the Tauri
shell can spawn it as a sidecar with no system Python required.
"""
from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


SPEC_DIR = Path(SPECPATH).resolve()
BACKEND_ROOT = SPEC_DIR.parent
APP_PACKAGE = BACKEND_ROOT / "app"
ALEMBIC_DIR = BACKEND_ROOT / "alembic"
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"


datas = [
    (str(ALEMBIC_DIR), "alembic"),
    (str(ALEMBIC_INI), "."),
]
datas += collect_data_files("librosa")
datas += collect_data_files("soundfile")


hiddenimports: list[str] = []
hiddenimports += collect_submodules("app")
hiddenimports += collect_submodules("alembic")
hiddenimports += collect_submodules("librosa")
hiddenimports += collect_submodules("numba")
hiddenimports += [
    "psycopg2",
    "psycopg2.extensions",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
]


a = Analysis(
    [str(APP_PACKAGE / "desktop_launcher.py")],
    pathex=[str(BACKEND_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="synthbud-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
