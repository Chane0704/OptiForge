"""Over-The-Air (OTA) Update Service for OptiForge Desktop App.

Features:
1. Queries GitHub Releases API for new versions.
2. Compares semantic versioning.
3. Downloads the official Windows installer in the background with real progress tracking.
4. Seamlessly launches Inno Setup installer with /SILENT /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS
   to update the app without manual file manipulation, and auto-restarts into the new version.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import threading
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any
from optiforge import __version__

CURRENT_VERSION = __version__
REPO = "Chane0704/OptiForge"


class UpdateState:
    status: str = "idle"  # "idle" | "checking" | "available" | "downloading" | "ready" | "error"
    latest_version: str = ""
    release_name: str = ""
    release_notes: str = ""
    download_url: str = ""
    total_bytes: int = 0
    downloaded_bytes: int = 0
    progress_percent: int = 0
    downloaded_installer_path: Optional[Path] = None
    error_message: str = ""
    last_checked_time: Optional[str] = None


state = UpdateState()
_download_thread: Optional[threading.Thread] = None


def parse_version_tuple(v_str: str) -> tuple:
    """Converts a version string like 'v1.0.1' or '1.2.0' into a comparable tuple of ints."""
    clean = v_str.strip().lstrip("v").split("-")[0]
    parts = []
    for part in clean.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def check_for_updates() -> Dict[str, Any]:
    """Queries GitHub Releases API to see if a newer release exists."""
    global state
    state.status = "checking"
    state.error_message = ""
    state.last_checked_time = time.strftime("%I:%M %p")

    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"OptiForge-Desktop/{CURRENT_VERSION}",
            "Accept": "application/vnd.github+json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        tag = data.get("tag_name", "")
        latest_tuple = parse_version_tuple(tag)
        current_tuple = parse_version_tuple(CURRENT_VERSION)

        state.latest_version = tag.lstrip("v")
        state.release_name = data.get("name", f"OptiForge {tag}")
        state.release_notes = data.get("body", "")

        # Find the setup .exe asset
        setup_asset = None
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".exe") and ("Setup" in name or "setup" in name):
                setup_asset = asset
                break

        if not setup_asset and data.get("assets"):
            setup_asset = data["assets"][0]

        if setup_asset:
            state.download_url = setup_asset.get("browser_download_url", "")
            state.total_bytes = setup_asset.get("size", 0)

        update_available = latest_tuple > current_tuple

        if update_available and state.download_url:
            state.status = "available"
        else:
            state.status = "idle"

        return {
            "success": True,
            "update_available": update_available,
            "current_version": CURRENT_VERSION,
            "latest_version": state.latest_version,
            "release_name": state.release_name,
            "release_notes": state.release_notes,
            "download_url": state.download_url,
            "total_bytes": state.total_bytes,
            "total_mb": round(state.total_bytes / (1024 * 1024), 1) if state.total_bytes else 0,
            "last_checked": state.last_checked_time,
        }
    except Exception as e:
        state.status = "idle"
        state.error_message = str(e)
        return {
            "success": False,
            "update_available": False,
            "current_version": CURRENT_VERSION,
            "error": str(e),
            "last_checked": state.last_checked_time,
        }


def _background_download_worker():
    global state
    state.status = "downloading"
    state.downloaded_bytes = 0
    state.progress_percent = 0

    temp_dir = Path(tempfile.gettempdir()) / "OptiForgeUpdate"
    temp_dir.mkdir(parents=True, exist_ok=True)
    installer_path = temp_dir / f"OptiForge-Setup-{state.latest_version}.exe"

    try:
        req = urllib.request.Request(
            state.download_url,
            headers={"User-Agent": f"OptiForge-Desktop/{CURRENT_VERSION}"}
        )

        with urllib.request.urlopen(req, timeout=30) as resp, open(installer_path, "wb") as out_file:
            content_length = resp.headers.get("Content-Length")
            total = int(content_length) if content_length else state.total_bytes
            state.total_bytes = total

            downloaded = 0
            chunk_size = 65536  # 64 KB chunks

            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                state.downloaded_bytes = downloaded
                if total > 0:
                    state.progress_percent = int((downloaded / total) * 100)

        state.downloaded_installer_path = installer_path
        state.status = "ready"
        state.progress_percent = 100
    except Exception as e:
        state.status = "error"
        state.error_message = f"Download failed: {e}"


def start_download() -> Dict[str, Any]:
    """Initiates an asynchronous download of the new installer."""
    global _download_thread, state
    if not state.download_url:
        return {"success": False, "error": "No update download URL available."}

    if state.status == "downloading":
        return {"success": True, "message": "Download already in progress."}

    _download_thread = threading.Thread(target=_background_download_worker, daemon=True)
    _download_thread.start()
    return {"success": True, "message": "Download started."}


def get_update_status() -> Dict[str, Any]:
    """Returns the live download progress and state."""
    downloaded_mb = round(state.downloaded_bytes / (1024 * 1024), 2)
    total_mb = round(state.total_bytes / (1024 * 1024), 2)

    return {
        "status": state.status,
        "latest_version": state.latest_version,
        "progress_percent": state.progress_percent,
        "downloaded_mb": downloaded_mb,
        "total_mb": total_mb,
        "error": state.error_message,
        "installer_ready": state.downloaded_installer_path is not None and state.downloaded_installer_path.exists(),
    }


def apply_update() -> Dict[str, Any]:
    """Executes the installer silently with application restart flags and exits cleanly."""
    global state
    if not state.downloaded_installer_path or not state.downloaded_installer_path.exists():
        return {"success": False, "error": "Installer not found or download incomplete."}

    installer_file = str(state.downloaded_installer_path)

    # Inno Setup switches:
    # /SILENT: Suppresses wizard and background pages.
    # /CLOSEAPPLICATIONS: Gracefully closes running instances using files to be updated.
    # /RESTARTAPPLICATIONS: Restarts the updated app immediately after installation!
    # /NORESTART: Does not reboot computer.
    args = [installer_file, "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS", "/NORESTART"]

    try:
        # Launch detached from current process tree
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(args, creationflags=DETACHED_PROCESS, close_fds=True)

        # Schedule immediate clean exit so installer can replace files
        def delayed_exit():
            time.sleep(1.0)
            os._exit(0)

        threading.Thread(target=delayed_exit, daemon=True).start()
        return {"success": True, "message": "Installer launched. Restarting OptiForge..."}
    except Exception as e:
        return {"success": False, "error": f"Failed to launch installer: {e}"}
