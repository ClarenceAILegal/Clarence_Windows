#!/usr/bin/env python3
"""
Clarence desktop application.

Starts a local FastAPI server and opens a native window (pywebview).
Works as a project launcher *and* as a frozen standalone .app (AirDrop-ready).
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import traceback
from pathlib import Path


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")


def _bootstrap() -> None:
    """Configure import path + env before importing motion_bot."""
    if not _is_frozen():
        root = Path(__file__).resolve().parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        env_path = root / ".env"
        if env_path.exists():
            try:
                from dotenv import load_dotenv

                load_dotenv(env_path)
            except Exception:
                pass

    # Ensure user data dirs exist / seed demos (frozen)
    try:
        from motion_bot.paths import ensure_runtime_dirs, is_frozen, user_data_dir

        ensure_runtime_dirs()
        # Settings migration may read env once, then we drop shared keys
        from motion_bot.settings import load_settings

        load_settings()
        if is_frozen():
            # Standalone: never inherit a developer machine key via env
            os.environ.pop("XAI_API_KEY", None)
        else:
            # Dev desktop: after migration into user settings, drop env key
            os.environ.pop("XAI_API_KEY", None)
        # Point optional log consumers at user data
        os.environ.setdefault("MOTION_BOT_USER_DATA", str(user_data_dir()))
    except Exception:
        pass


_bootstrap()


def _log_path() -> Path:
    if sys.platform == "darwin":
        log_dir = Path.home() / "Library" / "Logs" / "Clarence"
    elif sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        log_dir = Path(base) / "Clarence" / "Logs"
    else:
        log_dir = Path.home() / ".local" / "share" / "clarence" / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        log_dir = Path.home()
    return log_dir / "clarence.log"


def _log(msg: str) -> None:
    line = msg.rstrip() + "\n"
    try:
        with _log_path().open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass
    try:
        print(line, end="", file=sys.stderr)
    except Exception:
        pass


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_ready(url: str, timeout: float = 25.0) -> bool:
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status < 500:
                    return True
        except Exception:
            time.sleep(0.15)
    return False


def _alert(message: str) -> None:
    _log(message)
    try:
        if sys.platform == "darwin":
            import subprocess

            safe = (
                message.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
            )
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display alert "Clarence" message "{safe}" as critical',
                ],
                check=False,
                capture_output=True,
            )
        elif sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "Clarence", 0x10)
    except Exception:
        pass


def main() -> int:
    _log(f"======== Clarence start frozen={_is_frozen()} ========")
    try:
        from motion_bot.paths import ROOT, is_frozen, user_data_dir

        _log(f"user_data={user_data_dir()}")
        _log(f"root={ROOT} frozen={is_frozen()}")
    except Exception as exc:
        _alert(f"Clarence failed to initialize paths:\n{exc}")
        return 1

    port = int(os.environ.get("CLARENCE_PORT") or _free_port())
    host = "127.0.0.1"
    base = f"http://{host}:{port}"

    if not os.environ.get("MOTION_BOT_SECRET_KEY"):
        import secrets

        os.environ["MOTION_BOT_SECRET_KEY"] = secrets.token_hex(32)

    os.environ.setdefault("MOTION_BOT_HTTPS", "0")
    os.environ["CLARENCE_DESKTOP"] = "1"

    try:
        import uvicorn
    except Exception as exc:  # noqa: BLE001
        _alert(f"Missing dependency (uvicorn): {exc}")
        return 1

    config = uvicorn.Config(
        "motion_bot.web.app:app",
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    if not _wait_ready(f"{base}/health"):
        _alert(
            "Clarence failed to start its local server.\n"
            f"See log:\n{_log_path()}"
        )
        return 1

    try:
        import webview
    except ImportError:
        _alert("pywebview is missing from this build of Clarence.")
        return 1

    try:
        webview.create_window(
            title="Clarence",
            url=f"{base}/login",
            width=1180,
            height=820,
            min_size=(900, 640),
            background_color="#000080",
        )
        webview.start(
            debug=bool(os.environ.get("CLARENCE_DEBUG")),
            private_mode=False,
        )
    except Exception as exc:  # noqa: BLE001
        _log(traceback.format_exc())
        _alert(f"Could not open Clarence window:\n{exc}")
        return 1
    finally:
        server.should_exit = True
    _log("Clarence exited normally")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        _log(traceback.format_exc())
        _alert(f"Clarence crashed.\nSee log:\n{_log_path()}")
        raise SystemExit(1)
