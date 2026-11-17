# ⚡ OptiForge: Universal Performance & Efficiency Optimizer

[![GitHub Release](https://img.shields.io/github/v/release/Chane0704/OptiForge?style=for-the-badge&logo=github&color=38bdf8)](https://github.com/Chane0704/OptiForge/releases)
[![Download Windows Installer](https://img.shields.io/badge/Download-Windows%20Setup%20(.exe)-brightgreen?logo=windows&style=for-the-badge)](https://github.com/Chane0704/OptiForge/releases/download/v1.0.0/OptiForge-Setup-1.0.0.exe)
[![Download Portable Zip](https://img.shields.io/badge/Download-Portable%20(.zip)-blue?logo=windows&style=for-the-badge)](https://github.com/Chane0704/OptiForge/releases/download/v1.0.0/OptiForge-v1.0.0-windows-x64.zip)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![Tests Passing](https://img.shields.io/badge/Tests-37%20Passed-success?style=for-the-badge)](https://github.com/Chane0704/OptiForge)

> **OptiForge** is an extensible, industry-grade performance analysis and optimization engine. It audits websites, local processes, and codebases to diagnose bottlenecks, eliminate bloat, prioritize fixes by ROI (Impact vs. Effort), and safely apply reversible optimizations with zero risk of data loss.

---

## 📥 Direct Downloads & Installation

| Package | Format | Compatibility | Size | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Windows Installer** | [**OptiForge-Setup-1.0.0.exe**](https://github.com/Chane0704/OptiForge/releases/download/v1.0.0/OptiForge-Setup-1.0.0.exe) | Windows 10/11 (x64) | ~25 MB | Recommended. Per-user install, Start Menu & Desktop shortcuts, clean uninstaller. No admin or Python needed. |
| **Portable Package** | [**OptiForge-v1.0.0-windows-x64.zip**](https://github.com/Chane0704/OptiForge/releases/download/v1.0.0/OptiForge-v1.0.0-windows-x64.zip) | Windows 10/11 (x64) | ~33 MB | No installation needed. Extract and run `OptiForgeApp.exe`. |
| **Python CLI Engine** | `pip install git+https://github.com/Chane0704/OptiForge.git` | Windows, macOS, Linux | Source | Full developer CLI suite (`optiforge analyze`, `fix`, `serve`). |
| **Integrity & Checksums** | [**CHECKSUMS.txt**](https://github.com/Chane0704/OptiForge/releases/download/v1.0.0/CHECKSUMS.txt) | All | Plaintext | SHA-256 hashes to verify downloads. See [Installation Guide](docs/INSTALL.md). |

---

## 🌟 Key Capabilities

### 1. Multi-Target Profiler & Analyzer
- **Local Processes & OS System**: Per-process and system-wide CPU %, RAM (RSS/VMS), thread count, OS handle counts, disk I/O rates, monotonic memory leak detection, hot loops, and high-idle waste.
- **Websites & Web Apps**: Live remote URLs or local web projects. Audits TTFB, gzip/brotli HTTP compression, cache-control directives, render-blocking scripts in `<head>`, and Core Web Vitals heuristics (Cumulative Layout Shift, First Contentful Paint).
- **Codebases & Stacks**: Python, JavaScript, TypeScript, and Docker container configurations.

### 2. Compression & Size Optimizer
- **Modern Image Conversion**: Automatically converts uncompressed BMP, TIFF, and oversized PNG/JPEG images into modern **WebP** / **AVIF** with tunable quality, reducing payload size by **70–95%**.
- **Code Minification**: In-process, safe minification of CSS, JavaScript, and HTML, stripping comments, excess whitespace, and syntax redundancy.
- **Before/After Byte-Level Accounting**: Reports exact bytes and percentage saved for every change.

### 3. Deep Waste Finder
- **Unused Dependencies**: Scans AST imports to identify unused packages in `package.json` (Node.js) and `requirements.txt` / `pyproject.toml` (Python).
- **Dead Code & Orphan Files**: Detects unreferenced internal functions and obsolete helper scripts.
- **Byte-for-Byte Duplicate Files**: Cryptographic SHA-256 two-tier hashing detects identical duplicate assets.
- **Unused CSS**: Cross-references stylesheet class selectors with HTML templates to isolate dead rules.
- **Docker Bloat**: Audits Dockerfiles for missing `.dockerignore` files and uncleaned package manager caches (`apt-get`).

### 4. Recommendations Engine (Impact vs. Effort)
- Computes an ROI efficiency score for each finding:
  $$\text{Score} = \left(\frac{\text{Impact} \times 10}{\text{Effort}}\right) \times \text{Confidence}$$
- Segregates findings into action quadrants:
  - **Quick Wins**: High Impact, Low Effort (First priority)
  - **Strategic Refactors**: High Impact, Moderate/High Effort
  - **Maintenance**: Low Impact, Low Effort
  - **Low Priority / Deferred**: Low Impact, High Effort

### 5. Safe Auto-Fix Engine & One-Command Rollback
- **Dry-Run by Default**: `optiforge fix` previews all changes; nothing is modified without `--apply`.
- **Never Delete Guarantee**: Obsolete or duplicate files are moved to `.optiforge/quarantine/<backup_id>/`, never unlinked.
- **Atomic Pre-Fix Snapshots**: Full copy of original files and SHA-256 hash manifest saved before touching disk.
- **One-Command Rollback**: `optiforge rollback` restores all files bit-for-bit to their pre-fix state with cryptographic hash verification.

### 6. Rich Visualizations & Reporting
- **Interactive Terminal UI**: High-fidelity tables, color-coded badges, and progress spinners via Rich.
- **Local Web Dashboard**: Built-in HTTP server (`http://localhost:8848`) with Chart.js charts and real-time filtering.
- **Export Formats**: Standalone Markdown (`--export-md report.md`), JSON (`--export-json report.json`), and self-contained HTML (`--export-html dashboard.html`).

---

## 🚀 Installation & Requirements

- Python **3.10+** (Fully compatible with Python 3.13)
- OS: Windows, Linux, or macOS

```bash
# Clone the repository
git clone https://github.com/Chane0704/OptiForge.git
cd OptiForge

# Install in development mode
pip install -e .
```

---

## 🖥️ For Non-Technical Users: OptiForge Desktop App

If you don't know what a terminal, PID, or dependency is, **OptiForge App** is built for you. You never need to touch the command line.

### Launching the App
```bash
optiforge app
# or run the compiled standalone executable: dist/OptiForgeApp.exe
```

```
+-----------------------------------------------------------------------------------+
|  ⚡ OptiForge                                          [☀️/🌙] [❓ Walkthrough] [⚙️]  |
+-----------------------------------------------------------------------------------+
|           Make your website, code, or pictures faster and lighter.                |
|                    No terminal or technical knowledge required.                   |
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   |         📂 Drag and drop any folder, files, or pictures here              |   |
|   |          [ 📁 Select Folder ]   [ 📄 Select Files ]   [ 🖼️ Add Pictures ]    |   |
|   +---------------------------------------------------------------------------+   |
|   Or paste code, config, or a website link:                                       |
|   [ https://mywebsite.com OR paste code...                                    ]   |
|                                                                                   |
|   [ Step 1: Add Project ]  ----->  [ Step 2: See Savings ]  ----->  [ Step 3: Fix ]|
+-----------------------------------------------------------------------------------+
```

### 1. Add Your Project (5 Simple Ways)
1. **Drag and Drop**: Drag any project folder, file, or image directly onto the window.
2. **Select Folder**: Click `📁 Select Folder` to pick your website or app directory.
3. **Select Files**: Pick one or multiple code files.
4. **Add Pictures**: Pick uncompressed PNG, JPG, or BMP images to shrink their size.
5. **Paste Code or Link**: Paste a website URL (e.g. `https://mywebsite.com`) or paste code directly into the text box.

*OptiForge automatically detects what you provided and runs the right diagnostics. You never have to choose a plugin or configuration.*

### 2. See Plain-Language Savings
- **Health Score**: A simple 0–100 score showing your project's overall efficiency.
- **Headline Summary**: Plain-English explanation (e.g. *"Your project could be 2.6 MB smaller and load faster"*).
- **Grouped Cards**:
  - **⚡ Quick Wins**: Safe, high-impact fixes you can apply right away.
  - **🛠️ Worth Doing**: Meaningful refactors (like async blocking fixes).
  - **💡 Optional**: General cleanup and housekeeping.
- **Advanced Details**: Click *"▼ Advanced details"* on any card if you want to inspect technical file paths, line numbers, and metrics.

### 3. Hand-off to Your AI Agent (Antigravity, Claude Code, Cursor, ChatGPT)
Click **"🤖 Copy prompt for my AI agent"** on any finding or for the entire report:
- **3 Task Modes**:
  1. *Fix only the safe stuff* (Zero risk of breaking things)
  2. *Fix everything found* (Complete refactor)
  3. *Explain each fix step-by-step* (Great for learning)
- **Short / Detailed Toggle**: Choose between a high-level summary or complete context.
- **Automated Secret Redaction**: OptiForge automatically scans and redacts API keys (`sk-...`, `AIza...`), passwords, `.env` blocks, and database credentials before generating the prompt. Nothing sensitive leaves your screen.
- Click **"📋 Copy Prompt"** to copy with one click, or **"💾 Save as .md file"**.

### 4. Safe In-App Auto-Fix & 1-Click Undo
- Click **"⚡ Let OptiForge fix the safe stuff"** to apply verified optimizations (such as WebP conversions and code minification).
- A snapshot backup is created automatically.
- Deprecated or duplicate files are moved to `.optiforge/quarantine/`, **never deleted**.
- If anything doesn't look right, click **"↩ Undo Last Fix"** to restore all original files bit-for-bit with cryptographic verification.

### 5. Local Privacy by Default (Optional AI Mode)
- **100% Offline**: By default, OptiForge never sends code or data off your machine.
- **Optional AI Mode**: In Settings, you can optionally supply your Gemini API key for deeper AI explanations. OptiForge always shows an exact preview of what would be sent before sending anything.

---

---

## 🛠️ CLI Usage & Examples

### 1. Analyze a Target

```bash
# Analyze a codebase (current directory)
optiforge analyze .

# Analyze a local project and export reports
optiforge analyze ./sample_bloated_project --export-md report.md --export-json report.json --export-html dashboard.html

# Analyze a running process by PID
optiforge analyze 18536 --duration 2.0

# Analyze host system resources
optiforge analyze system

# Audit a live website
optiforge analyze https://example.com
```

### 2. Preview and Apply Optimizations (Safe Mode)

```bash
# DRY-RUN: Preview proposed fixes and estimated savings (NO disk writes)
optiforge fix ./sample_bloated_project

# LIVE EXECUTION: Create pre-fix snapshot and apply approved fixes
optiforge fix ./sample_bloated_project --apply -y
```

### 3. Instant Rollback

```bash
# Roll back to the most recent snapshot
optiforge rollback

# Roll back to a specific backup ID
optiforge rollback --id backup-20261117-182625
```

### 4. Interactive Dashboard & Viewing Reports

```bash
# Start local live dashboard on http://localhost:8848
optiforge serve ./sample_bloated_project --port 8848

# View a generated Markdown or JSON report in your terminal
optiforge report report.json
optiforge report report.md
```

### 5. Inspect Registered Plugins

```bash
optiforge plugins
```

---

## ⚙️ Configuration (`optiforge.yaml`)

Customize thresholds, safety parameters, and ignore patterns in `optiforge.yaml`:

```yaml
version: "1.0"

general:
  safety_level: "safe"
  default_dry_run: true
  backup_dir: ".optiforge/backups"
  quarantine_dir: ".optiforge/quarantine"

thresholds:
  cpu_hot_percent: 75.0
  cpu_idle_high_percent: 15.0
  memory_leak_growth_mb: 20.0
  oversized_asset_kb: 500.0
  slow_ttfb_ms: 600.0
  large_bundle_kb: 300.0

ignore:
  paths:
    - "node_modules/**"
    - ".git/**"
    - "venv/**"
    - ".optiforge/**"
  packages:
    - "pip"
    - "setuptools"
```

---

## 🧩 Extending OptiForge: Writing a Custom Plugin

OptiForge's plugin architecture makes adding support for new languages or audits straightforward:

```python
from optiforge.core.plugin_base import AnalyzerPlugin
from optiforge.core.target import Target, TargetKind
from optiforge.core.finding import Finding, Category, Impact, Effort, Confidence
from optiforge.config import OptiConfig

class GoWastePlugin(AnalyzerPlugin):
    name = "go_waste_finder"
    description = "Finds unused Go modules in go.mod"
    target_kinds = [TargetKind.CODEBASE]

    def can_handle(self, target: Target) -> bool:
        return target.path is not None and (target.path / "go.mod").exists()

    def analyze(self, target: Target, config: OptiConfig):
        findings = []
        # Custom analysis logic here...
        return findings
```

Register your plugin in `optiforge.core.registry.registry.register(GoWastePlugin())`.

---

## 🧪 Testing

OptiForge is thoroughly covered by unit and integration tests:

```bash
pytest -v
```

All 35 tests verify:
- Desktop app service layer, input autodetection, and REST APIs
- AI prompt generation with automatic secret stripping
- System profiler and memory leak detection
- Local and remote website auditing
- Image re-encoding and code minification
- Dead code, AST imports, duplicate file cryptographic detection
- Safety snapshots, file quarantine, and bit-for-bit rollback
- End-to-end integration across `sample_bloated_project`
