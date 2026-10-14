# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the HomeMind AI desktop launcher (Windows).

Build on Windows 11 with the project venv active::

    pip install pyinstaller
    pyinstaller desktop/homemind.spec

Output: dist/HomeMindAI.exe — a single-file launcher that starts the
loopback-only FastAPI backend, opens the UI, and manages shutdown.

IMPORTANT: this spec has NOT been built or smoke-tested in this Linux
environment. Build and test it on Windows 11 before distributing:
run the exe, create a conversation, stop Ollama to see the error state,
then close the app and confirm no backend process remains.

Do NOT claim the installer works until that Windows smoke test passes.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821  (defined by PyInstaller)

hidden = []
hidden += collect_submodules("homemind")
hidden += [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "sqlalchemy.dialects.sqlite",
]

a = Analysis(  # noqa: F821
    [str(ROOT / "desktop" / "launch.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        (str(ROOT / "frontend"), "frontend"),
        (str(ROOT / "README.md"), "."),
        (str(ROOT / "PRIVACY.md"), "docs"),
    ],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="HomeMindAI",
    debug=False,
    strip=False,
    upx=True,
    console=True,  # keep console: shows backend status + errors
    icon=None,
)
