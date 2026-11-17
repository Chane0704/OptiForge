"""Desktop Application Launcher and Reliability Supervisor for OptiForge.

Handles single-instance mutex, native Win32 window icon binding,
custom AppUserModelID, persistent logging, and WebView2 runtime supervision.
"""

from __future__ import annotations

import ctypes
import logging
import os
import socket
import sys
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Optional

# Explicit Windows AppUserModelID so taskbar groups properly with the new icon
APP_ID = "OptiForge.UniversalOptimizer.App.1.0"
if os.name == "nt":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass

APP_NAME = "OptiForge"
WINDOW_TITLE = "OptiForge — Universal Performance & Efficiency"
MUTEX_NAME = "OptiForgeApp_SingleInstance_Mutex_Chane0704"

# Global mutex handle to prevent garbage collection
_mutex_handle = None


def setup_application_logging() -> Path:
    """Configures persistent logging in %LOCALAPPDATA%\\OptiForge\\logs."""
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        log_dir = Path(local_appdata) / "OptiForge" / "logs"
    else:
        log_dir = Path.home() / ".optiforge" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "optiforge.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Global uncaught exception hook
    def uncaught_handler(exctype, value, tb):
        logging.error("Uncaught exception:", exc_info=(exctype, value, tb))
        show_friendly_error(
            "OptiForge Error",
            f"An unexpected error occurred: {value}\n\nLog details saved to:\n{log_file}",
        )

    sys.excepthook = uncaught_handler
    return log_file


def show_friendly_error(title: str, message: str):
    """Displays a native Windows message box with plain-English explanation."""
    try:
        if os.name == "nt":
            # 0x10 = MB_ICONERROR, 0x0 = MB_OK
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
        else:
            print(f"[{title}] {message}", file=sys.stderr)
    except Exception:
        print(f"[{title}] {message}", file=sys.stderr)


def check_single_instance() -> bool:
    """Ensures only one instance of OptiForge is running at a time."""
    global _mutex_handle
    if os.name == "nt":
        try:
            _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
            last_error = ctypes.windll.kernel32.GetLastError()
            # ERROR_ALREADY_EXISTS = 183
            if last_error == 183:
                return False
            return True
        except Exception:
            return True
    return True


def startup_self_check() -> tuple[bool, str]:
    """Verifies that all critical runtime dependencies and dynamic DLLs are available."""
    # 1. Test pyexpat (common condensation failure on Windows)
    try:
        import pyexpat  # noqa: F401
    except ImportError as e:
        return False, f"Missing XML parser component (pyexpat): {e}. Please ensure Microsoft Visual C++ Redistributable is installed."

    # 2. Test SSL & Hashlib
    try:
        import ssl  # noqa: F401
        import hashlib  # noqa: F401
    except ImportError as e:
        return False, f"Missing security/encryption component: {e}."

    # 3. Test SQLite
    try:
        import sqlite3  # noqa: F401
    except ImportError as e:
        return False, f"Missing database engine (sqlite3): {e}."

    return True, "OK"


def find_free_port(start_port: int = 8849) -> int:
    """Finds an available local TCP port."""
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def get_icon_path() -> Path:
    """Locates the application .ico file across frozen and source modes."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        for cand in [
            exe_dir / "optiforge.ico",
            exe_dir / "_internal" / "optiforge.ico",
            exe_dir / "_internal" / "optiforge" / "app" / "static" / "optiforge.ico",
        ]:
            if cand.exists():
                return cand
    src_icon = Path(__file__).resolve().parent.parent.parent / "optiforge.ico"
    return src_icon


def apply_win32_window_icon(window_title: str, icon_file: Path):
    """Binds native Win32 icon directly to pywebview HWND using WM_SETICON."""
    if os.name != "nt" or not icon_file.exists():
        return

    WM_SETICON = 0x0080
    ICON_SMALL = 0
    ICON_BIG = 1
    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x00000010

    # Poll briefly for window creation to capture the HWND
    for _ in range(30):
        time.sleep(0.15)
        hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
        if hwnd:
            try:
                h_icon_big = ctypes.windll.user32.LoadImageW(
                    0, str(icon_file), IMAGE_ICON, 32, 32, LR_LOADFROMFILE
                )
                h_icon_small = ctypes.windll.user32.LoadImageW(
                    0, str(icon_file), IMAGE_ICON, 16, 16, LR_LOADFROMFILE
                )
                if h_icon_big:
                    ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_icon_big)
                if h_icon_small:
                    ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_icon_small)
                logging.info(f"Applied native Win32 window icon to HWND {hwnd}")
                return
            except Exception as e:
                logging.warning(f"Failed to apply Win32 window icon: {e}")
                return


def launch_app(port: Optional[int] = None, no_window: bool = False, initial_target: Optional[str] = None):
    """Starts the OptiForge desktop application server and native window."""
    log_file = setup_application_logging()
    logging.info("Starting OptiForge Desktop App...")

    # 1. Single Instance Check
    if not check_single_instance():
        logging.info("Another instance is already running. Opening existing interface.")
        webbrowser.open("http://127.0.0.1:8849")
        return

    # 2. Startup Self-Check
    healthy, err_msg = startup_self_check()
    if not healthy:
        logging.error(f"Startup self-check failed: {err_msg}")
        show_friendly_error(
            "OptiForge - Startup Check Failed",
            f"OptiForge encountered a missing system component:\n\n{err_msg}\n\nTechnical logs: {log_file}",
        )
        sys.exit(1)

    # 3. Import app server
    try:
        from optiforge.app.app_server import app, session
    except Exception as e:
        logging.error("Failed to load application server:", exc_info=True)
        show_friendly_error(
            "OptiForge - Load Failure",
            f"Failed to start internal services: {e}\n\nPlease check logs at: {log_file}",
        )
        sys.exit(1)

    active_port = port or find_free_port(8849)

    # 4. Start local bottle server in daemon thread
    server_thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=active_port, quiet=True),
        daemon=True,
    )
    server_thread.start()
    time.sleep(0.3)

    app_url = f"http://127.0.0.1:{active_port}"
    if initial_target:
        app_url += f"?target={urllib.parse.quote(initial_target)}"

    logging.info(f"Local server listening at {app_url}")

    if no_window:
        logging.info("Launching default web browser as requested.")
        webbrowser.open(app_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return

    # 5. Launch Native Window (with graceful Browser Fallback)
    native_window_success = False
    icon_file = get_icon_path()

    try:
        import webview
        logging.info("Initializing pywebview native window...")

        # Spawn background thread to apply Win32 window icon once HWND is created
        threading.Thread(
            target=apply_win32_window_icon,
            args=(WINDOW_TITLE, icon_file),
            daemon=True,
        ).start()

        window = webview.create_window(
            title=WINDOW_TITLE,
            url=app_url,
            width=1080,
            height=790,
            min_size=(820, 600),
            background_color="#faf8f5",  # Warm Editorial Alabaster
        )
        session.webview_window = window
        native_window_success = True
        webview.start()
    except Exception as e:
        logging.warning(
            f"Native desktop window (WebView2) could not start ({e}). Falling back to default web browser."
        )
        native_window_success = False

    # Browser Fallback if native window failed or could not initialize
    if not native_window_success:
        logging.info(f"Opening OptiForge in default browser at {app_url}")
        webbrowser.open(app_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Shutting down OptiForge.")


if __name__ == "__main__":
    no_win = "--no-window" in sys.argv or "--browser" in sys.argv or "--headless" in sys.argv
    port_val = None
    target_arg = None

    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            try:
                port_val = int(arg.split("=")[1])
            except ValueError:
                pass
        elif not arg.startswith("-") and target_arg is None:
            target_arg = arg

    if "--check-only" in sys.argv:
        healthy, check_msg = startup_self_check()
        print(f"Self-check: {check_msg}")
        sys.exit(0 if healthy else 1)

    launch_app(port=port_val, no_window=no_win, initial_target=target_arg)
