"""Project / install path helpers.

Dev: data lives in the Motion-Bot project folder.
Standalone .app: writable data lives in the user's Application Support
folder so each person on each Mac has their own library, output, and settings.
Bundled demo templates ship inside the app and are copied on first launch.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Optional


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")


def bundle_root() -> Path:
    """Read-only resources shipped with the app (or project root in dev)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    if getattr(sys, "frozen", False):
        # py2app / some layouts: resources next to executable
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    """Writable per-user data directory."""
    override = os.environ.get("MOTION_BOT_USER_DATA", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return home / "Library" / "Application Support" / "Clarence"
    if system == "Windows":
        base = os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
        return Path(base) / "Clarence"
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return Path(xdg) / "clarence"
    return home / ".local" / "share" / "clarence"


def _dev_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


# Writable root: user data when frozen; project tree when developing
ROOT = user_data_dir() if is_frozen() else _dev_project_root()
BUNDLE_ROOT = bundle_root()

TEMPLATES_DIR = ROOT / "templates"
SAMPLE_TEMPLATES_DIR = TEMPLATES_DIR / "sample"
LIBRARY_TEMPLATES_DIR = TEMPLATES_DIR / "library"
CASES_DIR = ROOT / "data" / "cases"
OUTPUT_DIR = ROOT / "output"
MANIFEST_PATH = TEMPLATES_DIR / "manifest.yaml"

# Optional bundled demos inside the .app (read-only)
BUNDLE_TEMPLATES_DIR = BUNDLE_ROOT / "templates"


def _copy_tree_files(src: Path, dest: Path) -> int:
    """Copy files from src into dest (no clobber of existing). Returns count copied."""
    if not src.is_dir():
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        target = dest / rel
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        n += 1
    return n


def seed_bundled_templates_if_needed() -> None:
    """First launch of standalone app: seed sample/library demos into user data."""
    if not BUNDLE_TEMPLATES_DIR.is_dir():
        return
    # Seed samples always if missing; library only if empty (practice-local after that)
    sample_src = BUNDLE_TEMPLATES_DIR / "sample"
    library_src = BUNDLE_TEMPLATES_DIR / "library"
    manifest_src = BUNDLE_TEMPLATES_DIR / "manifest.yaml"

    if sample_src.is_dir():
        _copy_tree_files(sample_src, SAMPLE_TEMPLATES_DIR)

    library_empty = not any(LIBRARY_TEMPLATES_DIR.glob("*.docx")) if LIBRARY_TEMPLATES_DIR.exists() else True
    if library_empty and library_src.is_dir():
        # Copy only .docx (skip huge sources/)
        LIBRARY_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        for docx in library_src.glob("*.docx"):
            dest = LIBRARY_TEMPLATES_DIR / docx.name
            if not dest.exists():
                shutil.copy2(docx, dest)
        readme = library_src / "README.md"
        if readme.exists() and not (LIBRARY_TEMPLATES_DIR / "README.md").exists():
            shutil.copy2(readme, LIBRARY_TEMPLATES_DIR / "README.md")

    if manifest_src.exists() and not MANIFEST_PATH.exists():
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest_src, MANIFEST_PATH)


def ensure_runtime_dirs() -> None:
    """Create directories the bot expects at runtime; seed demos when packaged."""
    for path in (
        TEMPLATES_DIR,
        SAMPLE_TEMPLATES_DIR,
        LIBRARY_TEMPLATES_DIR,
        CASES_DIR,
        OUTPUT_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
    if is_frozen():
        seed_bundled_templates_if_needed()
