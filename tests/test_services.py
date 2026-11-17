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


def test_misleading_detection_cases(tmp_path):
    """Verifies that misleading inputs are correctly classified and never falsely detected as websites."""
    detector = InputDetector()

    # 1. Folder containing index.html must be 'folder', NOT 'website'
    folder_with_html = tmp_path / "my_web_app"
    folder_with_html.mkdir()
    (folder_with_html / "index.html").write_text("<!DOCTYPE html><html><body>Test</body></html>", encoding="utf-8")
    d1 = detector.detect(str(folder_with_html))
    assert d1.input_type == "folder"
    assert d1.target.kind.value == "codebase"

    # 2. Code snippet containing a URL must be 'snippet', NOT 'website'
    snippet = "import requests\nresp = requests.get('https://api.github.com')\nprint(resp.status_code)"
    d2 = detector.detect(snippet)
    assert d2.input_type == "snippet"
    assert d2.input_type != "website"
    assert d2.target.kind.value == "codebase"

    # 3. File named site.html must be 'files', NOT 'website'
    site_file = tmp_path / "site.html"
    site_file.write_text("<html><h1>Site</h1></html>", encoding="utf-8")
    d3 = detector.detect(str(site_file))
    assert d3.input_type == "files"
    assert d3.input_type != "website"
    assert d3.target.kind.value == "codebase"

    # 4. Standalone URL IS a website
    d4 = detector.detect("https://example.com")
    assert d4.input_type == "website"
    assert d4.target.kind.value == "website"

    # 5. Non-existent path raises FileNotFoundError
    import pytest
    with pytest.raises(FileNotFoundError):
        detector.detect(str(tmp_path / "non_existent_path_12345"))


def test_three_projects_produce_different_real_metrics():
    """Verifies that 3 distinct targets produce distinct scores, findings, and measured metrics."""
    detector = InputDetector()
    service = AnalysisService()

    root = Path(__file__).resolve().parent.parent
    targets = [
        ("sample_bloated_project", root / "sample_bloated_project"),
        ("clean_project", root / "test_targets" / "clean_project"),
        ("minimal_project", root / "test_targets" / "minimal_project"),
    ]

    results = []
    for name, path in targets:
        detected = detector.detect(str(path))
        res = service.analyze(detected)
        results.append(res)

    # Bloated project
    bloated = results[0]
    clean = results[1]
    minimal = results[2]

    # Scores must all be different
    assert bloated.health_score != clean.health_score
    assert clean.health_score != minimal.health_score
    assert bloated.health_score != minimal.health_score

    # Clean project must have 100 health score and 0 findings
    assert clean.health_score == 100.0
    assert len(clean.all_findings) == 0
    assert clean.total_savings_mb == 0.0

    # Bloated project must have findings and real measured savings
    assert bloated.health_score < 80.0
    assert len(bloated.all_findings) > 5
    assert bloated.total_savings_mb > 1.0

    # Minimal project has exactly 1 finding and 0.01 MB savings
    assert minimal.health_score == 98.0
    assert len(minimal.all_findings) == 1
    assert minimal.total_savings_mb == 0.01

