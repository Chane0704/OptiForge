"""Comprehensive End-to-End Integration Test for OptiForge."""

import hashlib
import json
import shutil
from pathlib import Path
import pytest

from optiforge.config import OptiConfig
from optiforge.core.registry import registry, register_builtin_plugins
from optiforge.core.safety import SafetyEngine
from optiforge.core.target import Target, TargetKind
from optiforge.reporting.dashboard_server import export_standalone_dashboard
from optiforge.reporting.markdown_reporter import export_markdown_report


@pytest.fixture(autouse=True)
def setup_plugins():
    register_builtin_plugins()


def test_end_to_end_optimization_workflow(tmp_path):
    # 1. Copy sample_bloated_project to isolated test workspace
    workspace = tmp_path / "bloated_workspace"
    shutil.copytree("sample_bloated_project", workspace)

    target = Target(kind=TargetKind.CODEBASE, identifier=str(workspace), path=workspace)
    config = OptiConfig(project_root=workspace)

    # 2. Run analysis
    findings, telemetry = registry.analyze_target(target, config)
    assert len(findings) >= 5

    categories = {f.category.value for f in findings}
    assert "AssetBloat" in categories
    assert "DeadCode" in categories
    assert "UnusedDependency" in categories
    assert "RuntimeSmoothness" in categories

    # 3. Test Report Exporters
    json_path = workspace / "report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"findings": [f.to_dict() for f in findings]}, f)
    assert json_path.exists()

    md_path = workspace / "report.md"
    export_markdown_report(target, findings, telemetry, md_path)
    assert md_path.exists()
    assert "OptiForge Performance & Optimization Report" in md_path.read_text(encoding="utf-8")

    html_path = workspace / "dashboard.html"
    export_standalone_dashboard(target, findings, telemetry, html_path)
    assert html_path.exists()
    assert "OptiForge Dashboard" in html_path.read_text(encoding="utf-8")

    # 4. Record pre-fix file hashes
    heavy_bmp = workspace / "images" / "heavy_photo.bmp"
    assert heavy_bmp.exists()
    original_bmp_hash = hashlib.sha256(heavy_bmp.read_bytes()).hexdigest()

    # 5. Collect fix proposals
    proposals = registry.collect_fix_proposals(findings, target, config)
    assert len(proposals) >= 1

    # 6. Apply fixes safely
    safety = SafetyEngine(config=config)
    results = safety.apply_proposals(proposals, target)
    assert len(results) >= 1

    # Verify quarantine exists and heavy BMP was replaced by WebP
    assert (workspace / "images" / "heavy_photo.webp").exists()

    # 7. Execute Rollback
    rollback_res = safety.rollback()
    assert rollback_res["success"] is True
    assert rollback_res["restored_count"] >= 1

    # 8. Verify exact pre-fix bit-for-bit file restoration
    assert heavy_bmp.exists()
    assert hashlib.sha256(heavy_bmp.read_bytes()).hexdigest() == original_bmp_hash
    assert not (workspace / "images" / "heavy_photo.webp").exists()
