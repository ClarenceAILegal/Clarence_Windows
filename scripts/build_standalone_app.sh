#!/usr/bin/env bash
# Build a double-click, AirDrop-ready Clarence.app (standalone).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VENV_PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "Missing .venv — create it first: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
  exit 1
fi

echo "==> Ensuring build dependencies..."
"$VENV_PY" -m pip install -q -e .
"$VENV_PY" -m pip install -q 'pyinstaller>=6.0' pillow

echo "==> Building app icon..."
"$VENV_PY" "$ROOT/scripts/build_app_icon.py"

echo "==> Cleaning previous dist..."
rm -rf "$ROOT/build/pyinstaller" "$ROOT/dist/Clarence" "$ROOT/dist/Clarence.app" "$ROOT/dist/Clarence-AirDrop"

echo "==> Running PyInstaller (this can take a few minutes)..."
# Force native arm64 build on Apple Silicon so recipients on M-series Macs work
if [[ "$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" == "1" ]]; then
  /usr/bin/arch -arm64 "$VENV_PY" -m PyInstaller \
    --noconfirm \
    --distpath "$ROOT/dist" \
    --workpath "$ROOT/build/pyinstaller" \
    "$ROOT/packaging/clarence.spec"
else
  "$VENV_PY" -m PyInstaller \
    --noconfirm \
    --distpath "$ROOT/dist" \
    --workpath "$ROOT/build/pyinstaller" \
    "$ROOT/packaging/clarence.spec"
fi

APP="$ROOT/dist/Clarence.app"
if [[ ! -d "$APP" ]]; then
  echo "Build failed: $APP not found"
  exit 1
fi

echo "==> Ad-hoc code signing..."
codesign --force --deep --sign - "$APP" 2>/dev/null || true
xattr -cr "$APP" 2>/dev/null || true

# Friendly AirDrop folder with a short readme
OUT="$ROOT/dist/Clarence-AirDrop"
mkdir -p "$OUT"
rm -rf "$OUT/Clarence.app"
ditto "$APP" "$OUT/Clarence.app"
cat > "$OUT/How to open Clarence.txt" <<'TXT'
Clarence — private motion drafting (desktop)

On a Mac:
1. Open this folder.
2. Drag Clarence into Applications (optional) or leave it here.
3. Double-click Clarence.
   - If macOS blocks it: Right-click → Open → Open.
4. Password: B0ts4Justice  (case-sensitive)
5. Grok chat is optional. Each person adds their OWN API key in the bear menu
   (https://console.x.ai). Without a key, free built-in chat still works.
6. Upload the motion templates you use — your library stays on YOUR Mac only.

Your data lives in:
  ~/Library/Application Support/Clarence/

Logs (if something fails):
  ~/Library/Logs/Clarence/clarence.log
TXT

# Zip for AirDrop / email (optional convenience)
ZIP="$ROOT/dist/Clarence-macOS.zip"
rm -f "$ZIP"
(
  cd "$OUT"
  zip -ry "$ZIP" Clarence.app "How to open Clarence.txt"
)

echo ""
echo "============================================"
echo "Standalone app ready for AirDrop:"
echo "  $OUT/Clarence.app"
echo "  $ZIP"
echo ""
echo "AirDrop the .app or the .zip to a friend."
echo "They may need: Right-click → Open  (first launch)."
echo "============================================"
