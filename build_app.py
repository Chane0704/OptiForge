"""Unified Build and Distribution Script for OptiForge Desktop App.

Automates:
1. Conda runtime DLL discovery & dependency collection.
2. PyInstaller --onedir build with icon and assets.
3. Inno Setup installer compilation (OptiForge-Setup-1.0.0.exe).
4. Portable ZIP creation (OptiForge-v1.0.0-windows-x64.zip).
5. Cryptographic SHA-256 checksums generation.
6. Optional Authenticode code-signing.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

VERSION = "1.0.0"
APP_NAME = "OptiForgeApp"


def compute_sha256(filepath: Path) -> str:
    """Calculates SHA-256 hash for a given file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def find_inno_setup_compiler() -> Path | None:
    """Locates the Inno Setup command-line compiler (ISCC.exe)."""
    # 1. Check PATH
    which_iscc = shutil.which("iscc") or shutil.which("ISCC")
    if which_iscc:
        return Path(which_iscc)

    # 2. Check standard install directories
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")

    candidates = [
        Path(local_appdata) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(program_files_x86) / "Inno Setup 6" / "ISCC.exe",
        Path(program_files) / "Inno Setup 6" / "ISCC.exe",
    ]

    for cand in candidates:
        if cand.exists():
            return cand

    return None


def collect_conda_dlls() -> list[str]:
    """Detects Conda environments and collects required C-runtime DLLs from Library\\bin."""
    prefix = Path(sys.prefix)
    lib_bin = prefix / "Library" / "bin"
    add_binary_args = []

    if not lib_bin.exists():
        print("ℹ️ Standard Python detected (non-conda).")
        return add_binary_args

    print(f"🔍 Conda environment detected at {prefix}. Collecting runtime DLLs from Library/bin...")

    # Key DLLs needed by Python C-extensions in Conda on Windows
    target_dll_prefixes = [
        "libexpat", "ffi", "libbz2", "liblzma", "libcrypto", "libssl",
        "sqlite3", "zlib", "zstd", "libmpdec"
    ]

    found_count = 0
    for dll_file in lib_bin.glob("*.dll"):
        dll_lower = dll_file.name.lower()
        if any(dll_lower.startswith(p) for p in target_dll_prefixes):
            add_binary_args.append(f"--add-binary={dll_file}{os.pathsep}.")
            found_count += 1

    print(f"✓ Collected {found_count} Conda runtime DLLs for bundling.")
    return add_binary_args


def build():
    root = Path(__file__).parent.resolve()
    dist_dir = root / "dist"
    build_dir = root / "build"
    app_folder = dist_dir / APP_NAME
    installer_dir = root / "installer"

    print(f"============================================================")
    print(f"⚡ OptiForge v{VERSION} — Desktop App & Installer Builder")
    print(f"============================================================\n")

    # Step 1: Ensure icon exists
    icon_file = root / "optiforge.ico"
    if not icon_file.exists():
        print("Creating application icon...")
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (256, 256), color=(15, 23, 42, 255))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([8, 8, 248, 248], radius=48, fill=(15, 23, 42, 255), outline=(56, 189, 248, 255), width=6)
        bolt = [(138, 28), (82, 134), (128, 134), (108, 228), (178, 114), (136, 114)]
        draw.polygon(bolt, fill=(56, 189, 248, 255))
        img.save(str(icon_file), format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])

    # Step 2: PyInstaller --onedir build
    print("\n📦 [1/4] Running PyInstaller (--onedir)...")

    static_dir = root / "optiforge" / "app" / "static"
    dashboard_dir = root / "optiforge" / "dashboard"
    config_file = root / "optiforge.yaml"

    add_data_args = [
        f"--add-data={static_dir}{os.pathsep}optiforge/app/static",
        f"--add-data={dashboard_dir}{os.pathsep}optiforge/dashboard",
        f"--add-data={config_file}{os.pathsep}optiforge",
    ]

    conda_dll_args = collect_conda_dlls()

    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        f"--name={APP_NAME}",
        "--onedir",
        "--noconsole",
        f"--icon={icon_file}",
        *add_data_args,
        *conda_dll_args,
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
        "--hidden-import=pyexpat",
        "--hidden-import=sqlite3",
        "--clean",
        "--noconfirm",
        "optiforge/app/main.py",
    ]

    py_res = subprocess.run(pyinstaller_cmd, cwd=root)
    if py_res.returncode != 0:
        print("❌ PyInstaller build failed.")
        sys.exit(1)

    print(f"✓ App directory built at: {app_folder}")

    # Copy icon into app directory as well
    shutil.copy2(icon_file, app_folder / "optiforge.ico")

    # Step 3: Optional Code-Signing
    cert_path = os.environ.get("SIGNTOOL_CERT")
    cert_pass = os.environ.get("SIGNTOOL_PASSWORD")
    if cert_path and Path(cert_path).exists():
        print("\n🔏 Signing executable with Authenticode certificate...")
        signtool = shutil.which("signtool") or "signtool"
        sign_cmd = [signtool, "sign", "/f", cert_path]
        if cert_pass:
            sign_cmd.extend(["/p", cert_pass])
        sign_cmd.extend(["/t", "http://timestamp.digicert.com", str(app_folder / f"{APP_NAME}.exe")])
        subprocess.run(sign_cmd)
    else:
        print("\nℹ️ Code-signing skipped (SIGNTOOL_CERT environment variable not set).")

    # Step 4: Create Portable ZIP
    print("\n🗜️ [2/4] Packaging portable ZIP archive...")
    zip_filename = dist_dir / f"OptiForge-v{VERSION}-windows-x64.zip"
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zf:
        for root_path, dirs, files in os.walk(app_folder):
            for file in files:
                full_p = Path(root_path) / file
                arc_p = full_p.relative_to(dist_dir)
                zf.write(full_p, arc_p)
    print(f"✓ Portable ZIP created: {zip_filename} ({zip_filename.stat().st_size / (1024*1024):.1f} MB)")

    # Step 5: Inno Setup Compilation
    print("\n🛠️ [3/4] Building Windows Installer with Inno Setup...")
    iscc_path = find_inno_setup_compiler()
    installer_exe = dist_dir / f"OptiForge-Setup-{VERSION}.exe"

    if iscc_path:
        iss_file = installer_dir / "optiforge.iss"
        iscc_cmd = [str(iscc_path), f"/DMyAppVersion={VERSION}", str(iss_file)]
        iscc_res = subprocess.run(iscc_cmd, cwd=root)
        if iscc_res.returncode == 0 and installer_exe.exists():
            print(f"✓ Windows Installer created: {installer_exe} ({installer_exe.stat().st_size / (1024*1024):.1f} MB)")
        else:
            print("⚠️ Inno Setup compilation failed or installer not produced.")
    else:
        print("⚠️ Inno Setup compiler (ISCC.exe) not found on system. Skipping installer compilation.")

    # Step 6: Generate SHA-256 Checksums
    print("\n🔒 [4/4] Generating SHA-256 Checksums...")
    checksum_file = dist_dir / "CHECKSUMS.txt"
    checksum_lines = []

    for target_artifact in [installer_exe, zip_filename]:
        if target_artifact.exists():
            sha = compute_sha256(target_artifact)
            checksum_lines.append(f"{sha}  {target_artifact.name}")
            print(f"  {target_artifact.name}: {sha}")

    checksum_file.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(f"✓ Wrote {checksum_file}")

    print("\n============================================================")
    print(f"🎉 Build Complete! Artifacts ready in dist/")
    print(f"============================================================")


if __name__ == "__main__":
    build()
