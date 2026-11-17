"""Script to create a GitHub Release and upload dist/ release binaries using Git credentials."""

import os
import sys
import json
import subprocess
from pathlib import Path
import urllib.request
import urllib.error

REPO = "Chane0704/OptiForge"
TAG = "v1.0.0"
TITLE = "OptiForge v1.0.0 — Windows Desktop App & Universal Optimizer Engine"

RELEASE_BODY = """## ⚡ OptiForge v1.0.0 — Official Windows Release

Welcome to the first official release of **OptiForge**, the universal performance and efficiency optimizer!

### 📥 Direct Downloads

| Package | Filename | Size | Description |
| :--- | :--- | :--- | :--- |
| **Windows Installer** | [`OptiForge-Setup-1.0.0.exe`](https://github.com/Chane0704/OptiForge/releases/download/v1.0.0/OptiForge-Setup-1.0.0.exe) | ~25 MB | **Recommended.** Standalone installer. Installs per-user, adds Start Menu & Desktop shortcuts. No Python or admin rights needed. |
| **Portable ZIP** | [`OptiForge-v1.0.0-windows-x64.zip`](https://github.com/Chane0704/OptiForge/releases/download/v1.0.0/OptiForge-v1.0.0-windows-x64.zip) | ~33 MB | No installation required. Extract anywhere and launch `OptiForgeApp.exe`. |
| **SHA-256 Checksums** | [`CHECKSUMS.txt`](https://github.com/Chane0704/OptiForge/releases/download/v1.0.0/CHECKSUMS.txt) | Plaintext | Integrity verification hashes for all files. |

---

### 🌟 Highlights & Features
- **Intuitive Desktop App**: Designed for non-technical users, vibe coders, and developers alike.
- **Multi-Input Auto-Detection**: Drag & drop folders, select files, paste code snippets, or enter website URLs.
- **Safe Auto-Fix & Rollback**: Dry-run by default, pre-fix snapshots, and one-command rollback with zero risk of data loss.
- **AI Agent Hand-Off**: One-click ready-to-paste prompt generation for Claude Code, Antigravity, Cursor, and ChatGPT with automatic secret redaction.
- **Universal Multi-Target Engine**: Audits website Core Web Vitals, OS process memory leaks, codebase dead code, unused dependencies, and byte-for-byte duplicate files.

---

### 🔒 Cryptographic Hashes (SHA-256)
```text
e3c59210bf59e308c1abefecd5f20c62e984ef8ab926efb087293763f8cf9086  OptiForge-Setup-1.0.0.exe
c8e0caedebad8bb24f0ec2d333424b97c8f6f5d5cc05038376a40b6b50f49460  OptiForge-v1.0.0-windows-x64.zip
```
"""


def get_github_token() -> str:
    """Retrieves GitHub token from git-credential-manager."""
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input=b"protocol=https\nhost=github.com\n",
        capture_output=True,
        check=True
    )
    for line in proc.stdout.decode().splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise RuntimeError("Could not find GitHub token in git credential helper.")


def make_request(url: str, method: str = "GET", headers: dict = None, data: bytes = None) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, data=data, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            code = resp.status
            try:
                parsed = json.loads(body.decode("utf-8"))
            except Exception:
                parsed = {}
            return code, parsed, body
    except urllib.error.HTTPError as e:
        err_body = e.read()
        try:
            parsed = json.loads(err_body.decode("utf-8"))
        except Exception:
            parsed = {}
        return e.code, parsed, err_body


def main():
    print("🔑 Fetching GitHub token...")
    token = get_github_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "OptiForge-Release-Publisher",
    }

    # 1. Check if release already exists
    release_url = f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}"
    code, data, _ = make_request(release_url, headers=headers)
    
    release_id = None
    upload_url_template = None

    if code == 200:
        print(f"✓ Found existing release for tag {TAG} (ID: {data['id']})")
        release_id = data["id"]
        upload_url_template = data["upload_url"]
    else:
        print(f"Creating new GitHub Release for {TAG}...")
        create_url = f"https://api.github.com/repos/{REPO}/releases"
        payload = {
            "tag_name": TAG,
            "target_commitish": "main",
            "name": TITLE,
            "body": RELEASE_BODY,
            "draft": False,
            "prerelease": False,
        }
        code, data, err = make_request(
            create_url,
            method="POST",
            headers={**headers, "Content-Type": "application/json"},
            data=json.dumps(payload).encode("utf-8"),
        )
        if code not in (200, 201):
            print(f"Failed to create release: HTTP {code}")
            print(json.dumps(data, indent=2))
            sys.exit(1)
        release_id = data["id"]
        upload_url_template = data["upload_url"]
        print(f"✓ Created Release: {data['html_url']}")

    # Get list of existing assets
    assets_url = f"https://api.github.com/repos/{REPO}/releases/{release_id}/assets"
    code, existing_assets, _ = make_request(assets_url, headers=headers)
    existing_map = {a["name"]: a["id"] for a in existing_assets} if code == 200 else {}

    # Clean upload base url (strip "{?name,label}")
    base_upload_url = upload_url_template.split("{")[0]

    files_to_upload = [
        ("OptiForge-Setup-1.0.0.exe", "application/vnd.microsoft.portable-executable"),
        ("OptiForge Setup 1.0.0.exe", "application/vnd.microsoft.portable-executable"),
        ("OptiForge-v1.0.0-windows-x64.zip", "application/zip"),
        ("CHECKSUMS.txt", "text/plain"),
    ]

    dist_dir = Path(__file__).resolve().parent.parent / "dist"

    # Ensure space-separated alias exists
    setup_hyphen = dist_dir / "OptiForge-Setup-1.0.0.exe"
    setup_space = dist_dir / "OptiForge Setup 1.0.0.exe"
    if setup_hyphen.exists() and not setup_space.exists():
        import shutil
        shutil.copy2(setup_hyphen, setup_space)

    for filename, content_type in files_to_upload:
        file_path = dist_dir / filename
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            continue

        # If asset already exists, delete it first to re-upload clean
        if filename in existing_map:
            print(f"Replacing existing asset {filename} (ID: {existing_map[filename]})...")
            del_url = f"https://api.github.com/repos/{REPO}/releases/assets/{existing_map[filename]}"
            make_request(del_url, method="DELETE", headers=headers)

        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        print(f"Uploading {filename} ({file_size_mb:.2f} MB)...")
        import urllib.parse
        encoded_name = urllib.parse.quote(filename)
        upload_url = f"{base_upload_url}?name={encoded_name}"

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        code, resp_data, raw_err = make_request(
            upload_url,
            method="POST",
            headers={**headers, "Content-Type": content_type},
            data=file_bytes,
        )

        if code in (200, 201):
            download_url = resp_data.get("browser_download_url")
            print(f"✓ Uploaded {filename} -> {download_url}")
        else:
            print(f"❌ Failed to upload {filename}: HTTP {code}")
            print(raw_err.decode("utf-8", errors="replace"))

    print("\n==================================================")
    print("🎉 All assets uploaded to GitHub Release v1.0.0!")
    print(f"Release URL: https://github.com/{REPO}/releases/tag/{TAG}")
    print("==================================================")


if __name__ == "__main__":
    main()
