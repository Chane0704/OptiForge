"""Desktop Application Launcher and Reliability Supervisor for OptiForge."""

from __future__ import annotations

import ctypes
import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

APP_NAME = "OptiForge"
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
            # Create or open named Windows mutex
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


def launch_app(port: Optional[int] = None, no_window: bool = False):
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
    try:
        import webview
        logging.info("Initializing pywebview native window...")
        window = webview.create_window(
            title="OptiForge — Universal Performance & Efficiency",
            url=app_url,
            width=1060,
            height=780,
            min_size=(800, 600),
            background_color="#0b0f19",
        )
        session.webview_window = window
        # Test start
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
            # Keep process alive while user uses the browser interface
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Shutting down OptiForge.")


if __name__ == "__main__":
    no_win = "--no-window" in sys.argv or "--browser" in sys.argv or "--headless" in sys.argv
    port_val = None
    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            try:
                port_val = int(arg.split("=")[1])
            except ValueError:
                pass
    if "--check-only" in sys.argv:
        healthy, check_msg = startup_self_check()
        print(f"Self-check: {check_msg}")
        sys.exit(0 if healthy else 1)
    launch_app(port=port_val, no_window=no_win)
