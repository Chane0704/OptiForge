"""Local Web Server for the OptiForge Desktop App."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
import bottle

from optiforge.config import OptiConfig
from optiforge.core.finding import FixProposal
from optiforge.services.ai_service import AIService
from optiforge.services.analysis_service import AnalysisService, FriendlyAnalysisResult
from optiforge.services.input_detector import DetectedInput, InputDetector
from optiforge.services.prompt_service import PromptService

logger = logging.getLogger("optiforge.app_server")

app = bottle.Bottle()
STATIC_DIR = Path(__file__).parent / "static"

# In-memory session state for active UI session
class AppSession:
    latest_result: Optional[FriendlyAnalysisResult] = None
    latest_proposals: List[FixProposal] = []
    active_target: Any = None
    webview_window: Any = None
    ai_service: AIService = AIService()

session = AppSession()


@app.route("/")
def index():
    return bottle.static_file("index.html", root=str(STATIC_DIR))


@app.route("/static/<filepath:path>")
def serve_static(filepath):
    return bottle.static_file(filepath, root=str(STATIC_DIR))


@app.route("/api/detect", method="POST")
def api_detect():
    try:
        data = bottle.request.json or {}
        raw = data.get("raw_input", "")
        detected = InputDetector.detect(raw)
        return {
            "success": True,
            "detected": {
                "input_type": detected.input_type,
                "friendly_label": detected.friendly_label,
                "item_count": detected.item_count,
                "estimated_size_bytes": detected.estimated_size_bytes,
                "target_identifier": detected.target.identifier,
                "language": detected.language,
            }
        }
    except Exception as e:
        logger.error(f"Detection failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@app.route("/api/analyze", method="POST")
def api_analyze():
    try:
        data = bottle.request.json or {}
        raw = data.get("raw_input", "")
        if not raw:
            return {"success": False, "error": "No input provided to analyze."}

        detected = InputDetector.detect(raw)
        config = OptiConfig.load()
        result = AnalysisService.analyze(detected, config=config)

        # Cache session result
        session.latest_result = result
        session.active_target = detected.target
        session.latest_proposals = AnalysisService.get_fix_proposals(
            detected.target, result.all_findings, config=config
        )

        return {
            "success": True,
            "result": result.to_dict(),
        }
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return {"success": False, "error": f"Analysis error: {str(e)}"}


@app.route("/api/generate-prompt", method="POST")
def api_generate_prompt():
    try:
        if not session.latest_result:
            return {"success": False, "error": "No active analysis to generate a prompt for."}

        data = bottle.request.json or {}
        mode = data.get("mode", "fix_safe")
        detail_level = data.get("detail_level", "detailed")
        finding_id = data.get("finding_id")

        if finding_id:
            # Single finding prompt
            all_friendly = (
                session.latest_result.quick_wins +
                session.latest_result.worth_doing +
                session.latest_result.optional
            )
            matching = [f for f in all_friendly if f.id == finding_id]
            if not matching:
                return {"success": False, "error": f"Finding {finding_id} not found."}

            res = PromptService.generate_prompt_for_single_finding(
                matching[0],
                target_name=session.latest_result.detected_input.friendly_label,
                mode=mode,
                detail_level=detail_level,
            )
        else:
            # Full report prompt
            res = PromptService.generate_full_report_prompt(
                session.latest_result,
                mode=mode,
                detail_level=detail_level,
            )

        return {
            "success": True,
            "prompt_text": res.prompt_text,
            "secrets_redacted_count": res.secrets_redacted_count,
            "redaction_warning": res.redaction_warning,
            "target_name": res.target_name,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.route("/api/fix/preview", method="GET")
def api_fix_preview():
    try:
        proposals_data = [p.to_dict() for p in session.latest_proposals]
        total_savings = sum(p.estimated_savings_bytes for p in session.latest_proposals)
        return {
            "success": True,
            "proposals": proposals_data,
            "total_savings_mb": round(total_savings / (1024 * 1024), 2),
            "count": len(session.latest_proposals),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.route("/api/fix/apply", method="POST")
def api_fix_apply():
    try:
        if not session.active_target or not session.latest_proposals:
            return {"success": False, "error": "No fixes available to apply."}

        data = bottle.request.json or {}
        filter_mode = data.get("mode", "safe_only")

        to_apply = session.latest_proposals
        if filter_mode == "safe_only" and session.latest_result:
            safe_ids = {
                f.id for f in (session.latest_result.quick_wins + session.latest_result.worth_doing)
                if f.safety_badge == "Safe"
            }
            to_apply = [p for p in session.latest_proposals if p.finding_id in safe_ids]

        results = AnalysisService.apply_fixes(session.active_target, to_apply)
        successful = [r for r in results if r.success]
        saved_bytes = sum(r.bytes_saved for r in successful)

        return {
            "success": True,
            "applied_count": len(successful),
            "total_count": len(results),
            "bytes_saved_mb": round(saved_bytes / (1024 * 1024), 2),
            "results": [r.to_dict() for r in results],
        }
    except Exception as e:
        logger.error(f"Fix apply error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@app.route("/api/fix/rollback", method="POST")
def api_fix_rollback():
    try:
        data = bottle.request.json or {}
        backup_id = data.get("backup_id")
        res = AnalysisService.rollback_latest()
        return res
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.route("/api/dialog/pick", method="POST")
def api_dialog_pick():
    """Triggers native OS file/folder picker dialog."""
    try:
        data = bottle.request.json or {}
        dialog_type = data.get("dialog_type", "folder")

        # 1. If pywebview window exists, use native webview file dialog
        if session.webview_window:
            import webview
            if dialog_type == "folder":
                result = session.webview_window.create_file_dialog(webview.FOLDER_DIALOG)
            elif dialog_type == "images":
                result = session.webview_window.create_file_dialog(
                    webview.OPEN_DIALOG,
                    allow_multiple=True,
                    file_types=("Image Files (*.png;*.jpg;*.jpeg;*.bmp;*.webp)", "All Files (*.*)")
                )
            else:  # files
                result = session.webview_window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)

            if result:
                selected = result[0] if len(result) == 1 else list(result)
                return {"success": True, "selected": selected}
            return {"success": False, "cancelled": True}

        # 2. Fallback using PowerShell on Windows
        if os.name == "nt":
            if dialog_type == "folder":
                cmd = "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null; $d = New-Object System.Windows.Forms.FolderBrowserDialog; if ($d.ShowDialog() -eq 'OK') { Write-Output $d.SelectedPath }"
            else:
                cmd = "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null; $d = New-Object System.Windows.Forms.OpenFileDialog; $d.Multiselect = $true; if ($d.ShowDialog() -eq 'OK') { Write-Output $d.FileNames }"

            proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=30)
            paths = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            if paths:
                selected = paths[0] if len(paths) == 1 else paths
                return {"success": True, "selected": selected}

        return {"success": False, "cancelled": True}
    except Exception as e:
        logger.error(f"Dialog error: {e}")
        return {"success": False, "error": str(e)}


@app.route("/api/ai/preview", method="POST")
def api_ai_preview():
    try:
        data = bottle.request.json or {}
        text = data.get("text", "")
        img = data.get("image_path")
        return {"success": True, "preview": session.ai_service.preview_payload(text, img)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.route("/api/ai/explain", method="POST")
def api_ai_explain():
    try:
        data = bottle.request.json or {}
        finding_id = data.get("finding_id")
        api_key = data.get("api_key")
        if not api_key:
            return {"success": False, "error": "No API key supplied. Please set your key in Settings."}

        session.ai_service.api_key = api_key
        session.ai_service.enabled = True

        all_friendly = (
            session.latest_result.quick_wins +
            session.latest_result.worth_doing +
            session.latest_result.optional
        ) if session.latest_result else []

        matching = [f for f in all_friendly if f.id == finding_id]
        if not matching:
            return {"success": False, "error": "Finding not found."}

        return session.ai_service.explain_finding(matching[0])
    except Exception as e:
        return {"success": False, "error": str(e)}
