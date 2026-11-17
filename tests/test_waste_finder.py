"""Tests for WasteFinderPlugin."""

from pathlib import Path
import pytest
from optiforge.config import OptiConfig
from optiforge.core.finding import Category
from optiforge.core.target import Target, TargetKind
from optiforge.plugins.waste_finder import WasteFinderPlugin


@pytest.fixture
def target_sample():
    return Target(
        kind=TargetKind.CODEBASE,
        identifier="sample_bloated_project",
        path=Path("sample_bloated_project"),
    )


def test_waste_finder_duplicates(target_sample):
    plugin = WasteFinderPlugin()
    config = OptiConfig()
    findings = plugin.analyze(target_sample, config)

    dup_findings = [f for f in findings if f.category == Category.DUPLICATE_FILE]
    assert len(dup_findings) >= 1
    assert "heavy_photo.bmp" in dup_findings[0].description or "duplicate_photo.bmp" in dup_findings[0].description


def test_waste_finder_unused_node_deps(target_sample):
    plugin = WasteFinderPlugin()
    config = OptiConfig()
    findings = plugin.analyze(target_sample, config)

    node_dep_findings = [f for f in findings if f.category == Category.UNUSED_DEPENDENCY and "package.json" in str(f.target_path)]
    flagged_pkgs = {f.target_entity for f in node_dep_findings}

    # moment and faker are unused
    assert "moment" in flagged_pkgs
    assert "faker" in flagged_pkgs
    # lodash is used, so must NOT be flagged
    assert "lodash" not in flagged_pkgs


def test_waste_finder_unused_python_deps(target_sample):
    plugin = WasteFinderPlugin()
    config = OptiConfig()
    findings = plugin.analyze(target_sample, config)

    py_dep_findings = [f for f in findings if f.category == Category.UNUSED_DEPENDENCY and "requirements.txt" in str(f.target_path)]
    flagged_pkgs = {f.target_entity for f in py_dep_findings}

    # scipy and redis are unused
    assert "scipy" in flagged_pkgs
    assert "redis" in flagged_pkgs
    # requests and click are used, so must NOT be flagged
    assert "requests" not in flagged_pkgs
    assert "click" not in flagged_pkgs


def test_waste_finder_dead_code_python(target_sample):
    plugin = WasteFinderPlugin()
    config = OptiConfig()
    findings = plugin.analyze(target_sample, config)

    dead_funcs = [f for f in findings if f.category == Category.DEAD_CODE and "_unused_legacy_calculation" in f.title]
    assert len(dead_funcs) == 1


def test_waste_finder_orphan_script(target_sample):
    plugin = WasteFinderPlugin()
    config = OptiConfig()
    findings = plugin.analyze(target_sample, config)

    dead_files = [f for f in findings if f.category == Category.DEAD_CODE and "dead_legacy_helper.js" in str(f.target_path)]
    assert len(dead_files) == 1


def test_waste_finder_unused_css(target_sample):
    plugin = WasteFinderPlugin()
    config = OptiConfig()
    findings = plugin.analyze(target_sample, config)

    css_findings = [f for f in findings if f.id.startswith("OPT-CSS-")]
    assert len(css_findings) >= 1
    assert "unused-modal-window" in css_findings[0].description


def test_waste_finder_dockerfile_audit(target_sample):
    plugin = WasteFinderPlugin()
    config = OptiConfig()
    findings = plugin.analyze(target_sample, config)

    docker_findings = [f for f in findings if "Dockerfile" in f.target_entity or "dockerignore" in f.title.lower()]
    assert len(docker_findings) >= 1
