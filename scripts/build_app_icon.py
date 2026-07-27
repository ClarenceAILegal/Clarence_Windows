#!/usr/bin/env python3
"""Render Clarence angry-bear menu icon into a macOS .icns."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "packaging" / "macos"
WIN_DIR = ROOT / "packaging" / "windows"
ICNS_PATH = OUT_DIR / "AppIcon.icns"
ICO_PATH = WIN_DIR / "AppIcon.ico"
PREVIEW_PATH = OUT_DIR / "AppIcon-1024.png"

# Colors from the in-app bear CSS
EAR_HEAD = "#f3d4b0"
EAR_INNER = "#e8a090"
SNOUT = "#f7e2c9"
INK = "#1c1012"
BG = "#000080"  # login navy, matches Clarence brand


def _scale(x: float, size: int) -> float:
    return x * (size / 32.0)


def draw_bear(size: int) -> Image.Image:
    """Draw the 32×32 SVG bear scaled to `size`, on a navy rounded square."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded app-icon plate
    margin = int(size * 0.04)
    radius = int(size * 0.22)
    draw.rounded_rectangle(
        [margin, margin, size - margin - 1, size - margin - 1],
        radius=radius,
        fill=BG,
    )

    def s(v: float) -> float:
        return _scale(v, size)

    # Slight downward nudge so ears aren't clipped by rounded corners
    dy = s(0.4)

    def xy(x: float, y: float) -> tuple[float, float]:
        return s(x), s(y) + dy

    def circle(cx: float, cy: float, r: float, fill: str, outline: str | None = None, width: float = 0):
        x, y = xy(cx, cy)
        rr = s(r)
        bbox = [x - rr, y - rr, x + rr, y + rr]
        if outline and width > 0:
            draw.ellipse(bbox, fill=fill, outline=outline, width=max(1, int(round(width))))
        else:
            draw.ellipse(bbox, fill=fill)

    stroke = max(1, int(round(s(1.35))))

    # Ears
    circle(7.5, 8.5, 4.2, EAR_HEAD, INK, stroke)
    circle(24.5, 8.5, 4.2, EAR_HEAD, INK, stroke)
    circle(7.5, 8.5, 2.1, EAR_INNER)
    circle(24.5, 8.5, 2.1, EAR_INNER)

    # Head
    circle(16, 17, 10.5, EAR_HEAD, INK, stroke)

    # Angry brows
    brow_w = max(1, int(round(s(1.55))))
    for x1, y1, x2, y2 in (
        (9.2, 13.2, 14.2, 15.1),
        (22.8, 13.2, 17.8, 15.1),
    ):
        draw.line([xy(x1, y1), xy(x2, y2)], fill=INK, width=brow_w)

    # Eyes
    circle(12.2, 16.8, 1.35, INK)
    circle(19.8, 16.8, 1.35, INK)

    # Snout
    sx, sy = xy(16, 21.2)
    rx, ry = s(4.2), s(3.1)
    draw.ellipse(
        [sx - rx, sy - ry, sx + rx, sy + ry],
        fill=SNOUT,
        outline=INK,
        width=max(1, int(round(s(1.1)))),
    )

    # Nose
    nx, ny = xy(16, 20.3)
    nrx, nry = s(1.5), s(1.15)
    draw.ellipse([nx - nrx, ny - nry, nx + nrx, ny + nry], fill=INK)

    # Frown (quadratic approx with polyline)
    mouth_w = max(1, int(round(s(1.35))))
    pts = []
    for t in [i / 16 for i in range(17)]:
        # Q from 13.4,23.1 via 16,21.6 to 18.6,23.1
        x = (1 - t) ** 2 * 13.4 + 2 * (1 - t) * t * 16 + t**2 * 18.6
        y = (1 - t) ** 2 * 23.1 + 2 * (1 - t) * t * 21.6 + t**2 * 23.1
        pts.append(xy(x, y))
    draw.line(pts, fill=INK, width=mouth_w, joint="curve")

    return img


def build_icns() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    master = draw_bear(1024)
    master.save(PREVIEW_PATH)

    # iconutil iconset sizes (@2x retina pairs; build names without raw @ in source)
    at2 = chr(64) + "2x.png"
    sizes = {
        "icon_16x16.png": 16,
        "icon_16x16" + at2: 32,
        "icon_32x32.png": 32,
        "icon_32x32" + at2: 64,
        "icon_128x128.png": 128,
        "icon_128x128" + at2: 256,
        "icon_256x256.png": 256,
        "icon_256x256" + at2: 512,
        "icon_512x512.png": 512,
        "icon_512x512" + at2: 1024,
    }

    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "AppIcon.iconset"
        iconset.mkdir()
        for name, px in sizes.items():
            im = draw_bear(px)
            # Force PNG format because some names contain @2x
            im.save(iconset / name, format="PNG")
        # iconutil writes next to iconset
        out = Path(tmp) / "AppIcon.icns"
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(out)],
            check=True,
        )
        shutil.copy2(out, ICNS_PATH)

    return ICNS_PATH


def build_ico() -> Path:
    """Windows .ico with multiple sizes."""
    WIN_DIR.mkdir(parents=True, exist_ok=True)
    sizes = [16, 32, 48, 64, 128, 256]
    images = [draw_bear(px) for px in sizes]
    # Pillow saves multi-size ICO from the largest with sizes= list
    images[-1].save(
        ICO_PATH,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )
    return ICO_PATH


def build_all() -> None:
    # icns needs macOS iconutil; skip gracefully elsewhere
    if sys.platform == "darwin":
        try:
            print(f"Wrote {build_icns()}")
        except Exception as exc:  # noqa: BLE001
            print(f"icns skipped: {exc}")
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            draw_bear(1024).save(PREVIEW_PATH)
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        draw_bear(1024).save(PREVIEW_PATH)
        print(f"Preview {PREVIEW_PATH}")
    print(f"Wrote {build_ico()}")


if __name__ == "__main__":
    build_all()
