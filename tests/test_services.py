"""Tests for OptiForge Service Layer (InputDetector & AnalysisService)."""

from pathlib import Path
import pytest
from optiforge.config import OptiConfig
from optiforge.core.target import TargetKind
from optiforge.services.input_detector import InputDetector
from optiforge.services.analysis_service import AnalysisService


def test_input_detector_website():
    detected = InputDetector.detect("https://example.com/test")
    assert detected.input_type == "website"
    assert detected.target.kind == TargetKind.WEBSITE
    assert "example.com" in detected.friendly_label


def test_input_detector_folder():
    detected = InputDetector.detect("sample_bloated_project")
    assert detected.input_type == "folder"
    assert detected.target.kind == TargetKind.CODEBASE
    assert "sample_bloated_project" in detected.friendly_label


def test_input_detector_single_image():
    img_path = Path("sample_bloated_project/images/heavy_photo.bmp")
    detected = InputDetector.detect(str(img_path))
    assert detected.input_type == "image"
    assert "Picture" in detected.friendly_label


def test_input_detector_multi_files():
    f1 = Path("sample_bloated_project/package.json")
    f2 = Path("sample_bloated_project/requirements.txt")
    detected = InputDetector.detect([str(f1), str(f2)])
    assert detected.input_type == "files"
    assert detected.item_count == 2


def test_input_detector_pasted_snippet(tmp_path):
    snippet = "def calculate_tax(income):\n    return income * 0.2\n"
    detected = InputDetector.detect(snippet, scratch_dir=tmp_path)
    assert detected.input_type == "snippet"
    assert detected.language == "Python"
    assert detected.target.path is not None
    assert detected.target.path.exists()


def test_input_detector_process():
    detected = InputDetector.detect("pid:9999")
    assert detected.input_type == "process"
    assert detected.target.pid == 9999


def test_analysis_service_friendly_results():
    detected = InputDetector.detect("sample_bloated_project")
    result = AnalysisService.analyze(detected)

    # Health score check
    assert 0 <= result.health_score <= 100
    assert result.health_label != ""
    assert result.total_savings_mb > 0
    assert len(result.all_findings) > 0

    # Friendly cards checks
    all_friendly = result.quick_wins + result.worth_doing + result.optional
    assert len(all_friendly) == len(result.all_findings)

    first_card = all_friendly[0]
    assert first_card.friendly_title != ""
    assert first_card.why_it_matters != ""
    assert first_card.what_to_do != ""
    assert first_card.safety_badge in ("Safe", "Probably safe", "Be careful")
    assert first_card.estimated_gain != ""
    assert "finding_id" in first_card.advanced_details
