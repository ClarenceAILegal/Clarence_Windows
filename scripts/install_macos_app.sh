#!/usr/bin/env bash
# Build Clarence.app and install to /Applications
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="Clarence"
APP_SRC="$ROOT/packaging/macos/${APP_NAME}.app"
APP_DST="/Applications/${APP_NAME}.app"
VENV_PY="$ROOT/.venv/bin/python"
LOG_DIR="$HOME/Library/Logs/Clarence"

cd "$ROOT"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Missing venv at $VENV_PY"
  echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
  exit 1
fi

# Ensure deps
"$VENV_PY" -c "import webview, fastapi, dotenv" 2>/dev/null || {
  echo "Installing desktop dependencies..."
  "$VENV_PY" -m pip install -e . -q
}

echo "Building angry-bear app icon..."
"$VENV_PY" "$ROOT/scripts/build_app_icon.py"

ICNS="$ROOT/packaging/macos/AppIcon.icns"
if [[ ! -f "$ICNS" ]]; then
  echo "Icon build failed: $ICNS missing"
  exit 1
fi

echo "Assembling ${APP_NAME}.app..."
rm -rf "$APP_SRC"
mkdir -p "$APP_SRC/Contents/MacOS"
mkdir -p "$APP_SRC/Contents/Resources"

cp "$ICNS" "$APP_SRC/Contents/Resources/AppIcon.icns"

# Robust launcher: logs failures + shows a dialog if something breaks
cat > "$APP_SRC/Contents/MacOS/Clarence" <<EOF
#!/bin/bash
# Clarence desktop launcher (macOS .app entrypoint)
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:\$PATH"

ROOT="$ROOT"
LOG_DIR="$LOG_DIR"
LOG_FILE="\$LOG_DIR/clarence.log"
mkdir -p "\$LOG_DIR"

exec >>"\$LOG_FILE" 2>&1
echo "======== \$(date '+%Y-%m-%d %H:%M:%S') launch ========"
echo "USER=\$USER HOME=\$HOME"
echo "PWD will be \$ROOT"

alert() {
  /usr/bin/osascript -e "display alert \\"Clarence\\" message \\"\$1\\" as critical" >/dev/null 2>&1 || true
}

cd "\$ROOT" || {
  alert "Could not open project folder:\\n\$ROOT"
  exit 1
}

# Optional local .env for site password only.
# Grok API keys are per-user (Application Support) — do NOT export XAI_API_KEY
# from a shared project file so other machines cannot inherit your key.
if [[ -f "\$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "\$ROOT/.env" || true
  set +a
  # Drop any project-level API key so each user must use their own saved key
  unset XAI_API_KEY
  echo "Loaded .env (API keys are per-user; project XAI_API_KEY ignored)"
else
  echo "No .env file (optional)"
fi

PY="\$ROOT/.venv/bin/python"
if [[ ! -x "\$PY" ]]; then
  echo "Missing python: \$PY"
  alert "Python environment missing.\\n\\nOpen Terminal and run:\\ncd ~/Motion-Bot && python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
  exit 1
fi

# Prefer the venv interpreter; unbuffered so logs appear promptly
export PYTHONUNBUFFERED=1
export MOTION_BOT_HTTPS="\${MOTION_BOT_HTTPS:-0}"
export CLARENCE_DESKTOP=1

# Force native arm64 on Apple Silicon hardware.
# Double-clicking a shell-based .app often starts under Rosetta (x86_64),
# which then cannot load arm64 wheels like pydantic_core.
ARCH_PREFIX=()
if [[ "\$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" == "1" ]]; then
  ARCH_PREFIX=(/usr/bin/arch -arm64)
fi

echo "shell_uname=\$(uname -m) translated=\$(/usr/sbin/sysctl -n sysctl.proc_translated 2>/dev/null || echo 0)"
echo "Starting: \${ARCH_PREFIX[*]} \$PY \$ROOT/desktop_app.py"
if [[ \${#ARCH_PREFIX[@]} -gt 0 ]]; then
  echo "py_report=\$("\${ARCH_PREFIX[@]}" "\$PY" -c 'import platform; print(platform.machine())' 2>/dev/null || echo unknown)"
else
  echo "py_report=\$("\$PY" -c 'import platform; print(platform.machine())' 2>/dev/null || echo unknown)"
fi

# Run python; if it crashes, surface the error
if [[ \${#ARCH_PREFIX[@]} -gt 0 ]]; then
  run_cmd=("\${ARCH_PREFIX[@]}" "\$PY" "\$ROOT/desktop_app.py")
else
  run_cmd=("\$PY" "\$ROOT/desktop_app.py")
fi
if ! "\${run_cmd[@]}"; then
  code=\$?
  echo "desktop_app exited with \$code"
  tail -n 12 "\$LOG_FILE" > "\$LOG_DIR/last-error.txt" 2>/dev/null || true
  alert "Clarence failed to start (exit \$code).\\n\\nSee log:\\n\$LOG_FILE"
  exit "\$code"
fi
echo "Clarence exited normally"
EOF
chmod +x "$APP_SRC/Contents/MacOS/Clarence"

cat > "$APP_SRC/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleDisplayName</key>
  <string>Clarence</string>
  <key>CFBundleExecutable</key>
  <string>Clarence</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>live.clarenceai.desktop</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>Clarence</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleVersion</key>
  <string>2</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>LSArchitecturePriority</key>
  <array>
    <string>arm64</string>
    <string>x86_64</string>
  </array>
  <key>LSUIElement</key>
  <false/>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSSupportsAutomaticGraphicsSwitching</key>
  <true/>
  <key>CFBundleDocumentTypes</key>
  <array/>
</dict>
</plist>
PLIST

echo -n 'APPL????' > "$APP_SRC/Contents/PkgInfo"

echo "Installing to $APP_DST ..."
rm -rf "$APP_DST"
ditto "$APP_SRC" "$APP_DST"

# Clear quarantine + ad-hoc sign so double-click is more likely to work
xattr -cr "$APP_DST" 2>/dev/null || true
codesign --force --deep --sign - "$APP_DST" 2>&1 || true

# Register with Launch Services (Dock / Spotlight / open -a)
LSREG="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [[ -x "$LSREG" ]]; then
  "$LSREG" -f "$APP_DST" 2>/dev/null || true
fi

touch "$APP_DST"
mkdir -p "$LOG_DIR"

echo ""
echo "Installed: $APP_DST"
echo "Log file:  $LOG_DIR/clarence.log"
echo ""
echo "If double-click is blocked by macOS:"
echo "  1) Right-click Clarence in Applications"
echo "  2) Choose Open"
echo "  3) Click Open again in the dialog"
echo ""
echo "Or from Terminal:"
echo "  open -a Clarence"
