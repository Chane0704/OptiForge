# 📦 OptiForge Windows Installation & Troubleshooting Guide

This guide helps non-technical users, students, and creators install and run OptiForge on Windows.

---

## 🚀 Download & Installation Options

### Option 1: Windows Setup Installer (Recommended)
1. Download **`OptiForge-Setup-1.0.0.exe`** from the [GitHub Releases](https://github.com/Chane0704/OptiForge/releases).
2. Double-click the downloaded setup file.
3. Choose whether to install for your user account (default, no administrator rights needed) or for all users.
4. Check the box to add a Desktop shortcut if desired, and click **Finish** to open OptiForge!

### Option 2: Portable ZIP (No Installation Required)
1. Download **`OptiForge-v1.0.0-windows-x64.zip`**.
2. Right-click the `.zip` file and select **Extract All...**.
3. Open the extracted `OptiForgeApp` folder and double-click **`OptiForgeApp.exe`**.

---

## 🛡️ Windows SmartScreen & Antivirus Notices

### Why Does Windows SmartScreen Show "Windows Protected Your PC"?
When you run a new or open-source software release on Windows, you may see a blue SmartScreen warning dialog:

> *"Windows protected your PC — Microsoft Defender SmartScreen prevented an unrecognized app from starting."*

#### Why does this happen?
Microsoft SmartScreen flags apps that are new or built without an expensive commercial code-signing certificate (\$300–\$500/year). OptiForge is free, open-source software, and newly compiled releases have not yet established a global download reputation in Microsoft's cloud database.

#### How to safely proceed:
1. Click the text link that says **"More info"**.
2. Click the **"Run anyway"** button that appears.
3. OptiForge will launch normally.

---

## 🔍 How to Verify File Integrity
You can verify that your downloaded file was not altered or corrupted by checking its SHA-256 hash.

Open PowerShell in the folder where you downloaded the file and run:
```powershell
Get-FileHash OptiForge-Setup-1.0.0.exe -Algorithm SHA256
```
Compare the output string against the official hash in `CHECKSUMS.txt` published on the GitHub Release page.

---

## ❓ Frequently Asked Questions & Troubleshooting

### What if the window does not appear?
OptiForge contains an automatic self-healing fallback. If the Microsoft Edge WebView2 native window engine is busy or unavailable on your computer, OptiForge will automatically open the application interface in your default web browser (Edge, Chrome, Brave, Firefox) at `http://127.0.0.1:8849`.

### Where are the application logs located?
OptiForge saves diagnostic logs locally on your machine at:
```text
%LOCALAPPDATA%\OptiForge\logs\optiforge.log
```
You can view this file in Notepad if you ever need technical details.

### How do I uninstall OptiForge?
- Go to Windows **Settings $\rightarrow$ Apps $\rightarrow$ Installed apps**.
- Find **OptiForge** and click **Uninstall**.
- **Data Safety Guarantee:** The uninstaller will strictly remove the OptiForge application binaries. It will **never** touch or delete your project code, images, or the `.optiforge/` backup and quarantine folders.

---

## 🍎 macOS and Linux Builds
Standalone packages for macOS (`.dmg`) and Linux (`.AppImage` / Flatpak) are planned for upcoming releases. In the meantime, macOS and Linux users can run OptiForge directly with Python:
```bash
git clone https://github.com/Chane0704/OptiForge.git
cd OptiForge
pip install -e .
optiforge app
```
