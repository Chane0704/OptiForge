"""Tests for App Server endpoints and end-to-end desktop app flow."""

from pathlib import Path
import pytest
import shutil
import hashlib
from optiforge.app.app_server import app, session
from optiforge.services.input_detector import InputDetector
from optiforge.services.analysis_service import AnalysisService


def test_api_detect_endpoint():
    # Test via direct service integration
    detected = InputDetector.detect("https://example.com")
    assert detected.input_type == "website"

    folder_detected = InputDetector.detect("sample_bloated_project")
    assert folder_detected.input_type == "folder"


def test_end_to_end_app_workflow(tmp_path):
    # Setup temporary copy of sample_bloated_project
    workspace = tmp_path / "app_bloated_test"
    shutil.copytree("sample_bloated_project", workspace)

    # 1. Detect
    detected = InputDetector.detect(str(workspace))
    assert detected.input_type == "folder"

    # 2. Analyze
    from optiforge.config import OptiConfig
    config = OptiConfig(project_root=workspace)
    result = AnalysisService.analyze(detected, config=config)
    assert result.health_score > 0
    assert result.total_savings_mb > 0
    assert len(result.quick_wins) > 0

    # 3. Generate prompt
    from optiforge.services.prompt_service import PromptService
    prompt_res = PromptService.generate_full_report_prompt(result, mode="fix_safe")
    assert "Mandatory Safety Rules" in prompt_res.prompt_text

    # 4. Propose fixes
    proposals = AnalysisService.get_fix_proposals(detected.target, result.all_findings, config=config)
    assert len(proposals) > 0

    # Record original image hash
    heavy_bmp = workspace / "images" / "heavy_photo.bmp"
    orig_hash = hashlib.sha256(heavy_bmp.read_bytes()).hexdigest()

    # 5. Apply fixes safely
    results = AnalysisService.apply_fixes(detected.target, proposals, config=config)
    assert any(r.success for r in results)

    # 6. Verify Rollback restores original file
    rollback_res = AnalysisService.rollback_latest(config=config)
    assert rollback_res["success"] is True
    assert heavy_bmp.exists()
    assert hashlib.sha256(heavy_bmp.read_bytes()).hexdigest() == orig_hash
