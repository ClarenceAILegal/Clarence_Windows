# Build a double-click Clarence folder for Windows (run on a Windows PC).
# Usage (PowerShell):
#   cd path\to\Motion-Bot
#   .\scripts\build_standalone_app_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    Write-Host "Creating venv..."
    python -m venv .venv
    $VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
}

Write-Host "==> Installing dependencies..."
& $VenvPy -m pip install -q --upgrade pip
& $VenvPy -m pip install -q -e .
& $VenvPy -m pip install -q "pyinstaller>=6.0" pillow pywebview pythonnet

Write-Host "==> Building icons..."
& $VenvPy (Join-Path $Root "scripts\build_app_icon.py")

Write-Host "==> Cleaning previous dist..."
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $Root "build\pyinstaller-win")
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $Root "dist\Clarence")
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $Root "dist\Clarence-Windows")
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $Root "dist\Clarence-Windows.zip")

Write-Host "==> PyInstaller..."
& $VenvPy -m PyInstaller `
  --noconfirm `
  --distpath (Join-Path $Root "dist") `
  --workpath (Join-Path $Root "build\pyinstaller-win") `
  (Join-Path $Root "packaging\clarence-windows.spec")

$Built = Join-Path $Root "dist\Clarence"
if (-not (Test-Path (Join-Path $Built "Clarence.exe"))) {
    throw "Build failed: Clarence.exe not found in $Built"
}

$Out = Join-Path $Root "dist\Clarence-Windows"
New-Item -ItemType Directory -Force -Path $Out | Out-Null
Copy-Item -Recurse -Force $Built (Join-Path $Out "Clarence")

@"
Clarence for Windows — private motion drafting

1. Unzip if needed, then open the Clarence folder.
2. Double-click Clarence.exe
   - Windows may show SmartScreen: More info → Run anyway
3. Password: B0ts4Justice  (case-sensitive)
4. Grok chat is optional. Each person adds THEIR OWN API key in the bear menu
   (https://console.x.ai). Free built-in chat works without a key.
5. Upload the motion templates you use — library stays on THIS PC only.

Requirements:
- Windows 10 or 11
- Microsoft Edge WebView2 Runtime (usually already installed)
  Download: https://developer.microsoft.com/microsoft-edge/webview2/

Your data:
  %APPDATA%\Clarence\

Logs:
  %LOCALAPPDATA%\Clarence\Logs\clarence.log
"@ | Set-Content -Encoding UTF8 (Join-Path $Out "How to open Clarence.txt")

$Zip = Join-Path $Root "dist\Clarence-Windows.zip"
if (Test-Path $Zip) { Remove-Item $Zip }
Compress-Archive -Path (Join-Path $Out "*") -DestinationPath $Zip -Force

Write-Host ""
Write-Host "============================================"
Write-Host "Windows build ready:"
Write-Host "  $Out\Clarence\Clarence.exe"
Write-Host "  $Zip"
Write-Host "Email / AirDrop / share the zip."
Write-Host "============================================"
