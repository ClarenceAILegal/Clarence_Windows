# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: standalone Clarence for Windows (build ON Windows)
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

# SPECPATH is the directory containing this .spec (packaging/)
ROOT = Path(SPECPATH).resolve().parent

datas = []
binaries = []
hiddenimports = []

templates_dir = ROOT / "templates"
if templates_dir.is_dir():
    datas.append((str(templates_dir), "templates"))

for sub in ("templates", "static"):
    p = ROOT / "motion_bot" / "web" / sub
    if p.is_dir():
        datas.append((str(p), f"motion_bot/web/{sub}"))

for pkg in (
    "uvicorn",
    "webview",
    "anyio",
    "starlette",
    "fastapi",
    "jinja2",
    "docxtpl",
    "docx",
    "clr_loader",
    "pythonnet",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        try:
            hiddenimports += collect_submodules(pkg)
        except Exception:
            pass

hiddenimports += collect_submodules("motion_bot")
hiddenimports += [
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
    "multipart",
    "yaml",
    "openai",
    "httpx",
    "dotenv",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
]

icon = ROOT / "packaging" / "windows" / "AppIcon.ico"
if not icon.exists():
    icon = None

a = Analysis(
    [str(ROOT / "desktop_app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Clarence",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon) if icon else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Clarence",
)
