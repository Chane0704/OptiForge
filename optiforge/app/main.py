"""Desktop Application Launcher for OptiForge."""

from __future__ import annotations

import logging
import socket
import threading
import time
import webbrowser
from typing import Optional

logger = logging.getLogger("optiforge.app")


def find_free_port(start_port: int = 8849) -> int:
    """Finds an available local TCP port."""
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def launch_app(port: Optional[int] = None, no_window: bool = False):
    """Starts the OptiForge desktop application server and native window."""
    from optiforge.app.app_server import app, session

    active_port = port or find_free_port(8849)

    # Start bottle server in background thread
    server_thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=active_port, quiet=True),
        daemon=True
    )
    server_thread.start()
    time.sleep(0.4)

    app_url = f"http://127.0.0.1:{active_port}"
    print(f"⚡ OptiForge App running at: {app_url}")

    if no_window:
        webbrowser.open(app_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return

    # Try launching native pywebview window
    try:
        import webview
        window = webview.create_window(
            title="OptiForge — Universal Performance & Efficiency",
            url=app_url,
            width=1040,
            height=760,
            min_size=(800, 600),
            background_color="#0b0f19",
        )
        session.webview_window = window
        webview.start()
    except Exception as e:
        logger.warning(f"Native desktop window unavailable ({e}). Falling back to browser view.")
        webbrowser.open(app_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    launch_app()
