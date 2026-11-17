"""Build script to compile OptiForge into a standalone single-file Windows executable using PyInstaller."""

import os
import sys
import subprocess
from pathlib import Path

def build_executable():
    root = Path(__file__).parent.resolve()
    print("⚡ Building OptiForge Desktop App for Windows...")

    static_dir = root / "optiforge" / "app" / "static"
    dashboard_dir = root / "optiforge" / "dashboard"
    config_file = root / "optiforge.yaml"

    add_data_args = [
        f"--add-data={static_dir}{os.pathsep}optiforge/app/static",
        f"--add-data={dashboard_dir}{os.pathsep}optiforge/dashboard",
        f"--add-data={config_file}{os.pathsep}optiforge",
    ]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=OptiForgeApp",
        "--onefile",
        "--noconsole",
        *add_data_args,
        "--hidden-import=optiforge",
        "--hidden-import=optiforge.plugins.system_profiler",
        "--hidden-import=optiforge.plugins.website_analyzer",
        "--hidden-import=optiforge.plugins.compressor",
        "--hidden-import=optiforge.plugins.waste_finder",
        "--hidden-import=optiforge.plugins.runtime_tuner",
        "--hidden-import=bottle",
        "--hidden-import=webview",
        "--hidden-import=PIL",
        "--hidden-import=psutil",
        "optiforge/app/main.py",
    ]

    print(f"Running PyInstaller command...")
    res = subprocess.run(cmd, cwd=root)
    if res.returncode == 0:
        exe_path = root / "dist" / "OptiForgeApp.exe"
        print(f"\n✓ Successfully built standalone Windows executable: {exe_path}")
        if exe_path.exists():
            print(f"  Size: {exe_path.stat().st_size / (1024 * 1024):.1f} MB")
    else:
        print(f"\n❌ Build failed with exit code {res.returncode}")

if __name__ == "__main__":
    build_executable()
