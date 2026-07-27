# Clarence for Windows

Yes — Clarence can run as a **double-click Windows app**.  
A Windows binary **must be built on Windows** (or via GitHub Actions). You cannot produce a reliable `.exe` from a Mac alone.

## Option A — GitHub Actions (recommended if you have a GitHub repo)

1. Push this project to GitHub (private is fine). **Do not commit** `.env`.
2. On GitHub: **Actions → “Build Clarence (Windows)” → Run workflow**.
3. When it finishes, download the **Clarence-Windows** artifact (`Clarence-Windows.zip`).
4. Email / text / share that zip.

## Option B — Build on a Windows PC

```powershell
cd path\to\Motion-Bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pip install pyinstaller pillow pywebview pythonnet
.\scripts\build_standalone_app_windows.ps1
```

Output:
- `dist\Clarence-Windows\Clarence\Clarence.exe`
- `dist\Clarence-Windows.zip` ← send this

Or double-click: `scripts\build_standalone_app_windows.bat`

## What recipients do

1. Unzip `Clarence-Windows.zip`
2. Open the **Clarence** folder
3. Double-click **`Clarence.exe`**
4. If SmartScreen appears: **More info → Run anyway**
5. Password: **`B0ts4Justice`**
6. Optional Grok: each person adds **their own** key in the bear menu

### Requirements
- Windows 10 or 11  
- [Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) (usually already installed)

### Their private data (not yours)
- Templates / output: `%APPDATA%\Clarence\`
- Logs: `%LOCALAPPDATA%\Clarence\Logs\clarence.log`
- API key: only on that PC, if they add one

## Dev run on Windows (without packaging)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
python desktop_app.py
```
