# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: standalone Clarence.app for AirDrop
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

# SPECPATH is the directory containing this .spec (packaging/)
ROOT = Path(SPECPATH).resolve().parent

datas = []
binaries = []
hiddenimports = []

# Bundle demo templates (seeded into each user's Application Support on first run)
templates_dir = ROOT / "templates"
if templates_dir.is_dir():
    datas.append((str(templates_dir), "templates"))

# Web UI assets (also in package-data; belt-and-suspenders)
for sub in ("templates", "static"):
    p = ROOT / "motion_bot" / "web" / sub
    if p.is_dir():
        datas.append((str(p), f"motion_bot/web/{sub}"))

# Heavy / dynamic packages
for pkg in ("uvicorn", "webview", "anyio", "starlette", "fastapi", "jinja2", "docxtpl", "docx"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        hiddenimports += collect_submodules(pkg)

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
    "email.mime.multipart",
    "pkg_resources.py2_warn",
    "yaml",
    "openai",
    "httpx",
    "dotenv",
]

icon = ROOT / "packaging" / "macos" / "AppIcon.icns"
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
    console=False,  # windowed double-click app
    disable_windowed_traceback=False,
    argv_emulation=True,  # better macOS .app behavior
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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

app = BUNDLE(
    coll,
    name="Clarence.app",
    icon=str(icon) if icon else None,
    bundle_identifier="live.clarenceai.desktop",
    version="0.1.0",
    info_plist={
        "CFBundleDisplayName": "Clarence",
        "CFBundleName": "Clarence",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "LSApplicationCategoryType": "public.app-category.productivity",
        "LSArchitecturePriority": ["arm64", "x86_64"],
        "NSAppleEventsUsageDescription": "Clarence opens generated Word documents in Finder.",
    },
)
