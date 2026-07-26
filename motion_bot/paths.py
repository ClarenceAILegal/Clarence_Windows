"""Project path helpers."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"
SAMPLE_TEMPLATES_DIR = TEMPLATES_DIR / "sample"
LIBRARY_TEMPLATES_DIR = TEMPLATES_DIR / "library"
CASES_DIR = ROOT / "data" / "cases"
OUTPUT_DIR = ROOT / "output"
MANIFEST_PATH = TEMPLATES_DIR / "manifest.yaml"


def ensure_runtime_dirs() -> None:
    """Create directories the bot expects at runtime."""
    for path in (
        TEMPLATES_DIR,
        SAMPLE_TEMPLATES_DIR,
        LIBRARY_TEMPLATES_DIR,
        CASES_DIR,
        OUTPUT_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
