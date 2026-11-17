import os
import sys
import time
from pathlib import Path

# Simulate running as v1.0.0 to test upgrading to v1.0.1
os.environ["OPTIFORGE_VERSION_OVERRIDE"] = "1.0.0"

from optiforge.services import updater_service

def run_test():
    print("==================================================")
    print("🧪 OptiForge OTA Live Update Flow Test")
    print("==================================================")

    # 1. Check for update
    print("\n🔍 [1/3] Checking for updates against GitHub Releases...")
    chk = updater_service.check_for_updates()
    print(f"  Success: {chk.get('success')}")
    print(f"  Update available: {chk.get('update_available')}")
    print(f"  Current version:  {chk.get('current_version')}")
    print(f"  Latest version:   {chk.get('latest_version')}")
    print(f"  Release name:     {chk.get('release_name')}")
    print(f"  Installer URL:    {chk.get('download_url')}")
    print(f"  Installer size:   {chk.get('total_mb')} MB")

    if not chk.get("update_available"):
        print("❌ FAILED: update_available was not True")
        sys.exit(1)

    # 2. Start background download
    print("\n📥 [2/3] Starting background streaming download...")
    dl_res = updater_service.start_download()
    print(f"  Start response: {dl_res}")

    # 3. Poll progress
    print("\n📊 [3/3] Tracking download progress live:")
    start_time = time.time()
    while time.time() - start_time < 30:
        time.sleep(0.4)
        status = updater_service.get_update_status()
        pct = status.get("progress_percent", 0)
        dl_mb = status.get("downloaded_mb", 0)
        tot_mb = status.get("total_mb", 0)
        curr_status = status.get("status")

        # Visual progress bar
        filled = int(pct / 5)
        bar = "█" * filled + "░" * (20 - filled)
        print(f"\r  [{bar}] {pct:3d}% ({dl_mb:5.1f} MB / {tot_mb:5.1f} MB) - Status: {curr_status}", end="", flush=True)

        if curr_status == "ready":
            print("\n\n🎉 SUCCESS! Installer downloaded and verified:")
            installer_path = updater_service.state.downloaded_installer_path
            print(f"  File: {installer_path}")
            print(f"  Exists: {installer_path.exists()}")
            print(f"  Size on disk: {installer_path.stat().st_size / (1024*1024):.2f} MB")
            return
        elif curr_status == "error":
            print(f"\n❌ FAILED: {status.get('error')}")
            sys.exit(1)

    print("\n⚠️ Download timed out after 30s")

if __name__ == "__main__":
    run_test()
