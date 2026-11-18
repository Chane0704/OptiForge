"""Regression tests for OptiForge Python dependency scanning and machine-readable output."""

import dataclasses
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from optiforge.analysis.python_deps import PythonDependencyAuditor
from optiforge.cli import cli
from optiforge.config import DependenciesConfig, OptiConfig
from optiforge.core.finding import Category, Confidence
from optiforge.core.safety import SafetyEngine
from optiforge.core.target import Target, TargetKind
from optiforge.plugins.waste_finder import WasteFinderPlugin


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tricky_python_project"


def test_tricky_python_project_zero_false_positives():
    """Validates that all tricky cases (dotenv, genai, yaml, PIL, requests[socks],

    typing-extensions, gunicorn, pytest) produce zero false positives, and only
    the genuinely dead package is flagged with high detection confidence.
    """
    config = OptiConfig()
    auditor = PythonDependencyAuditor(FIXTURE_DIR, config)
    findings = auditor.audit()

    # Must find EXACTLY one unused package
    assert len(findings) == 1, f"Expected 1 finding, got {len(findings)}: {[f.target_entity for f in findings]}"

    f = findings[0]
    assert f.target_entity == "unreferenced-zero-usage-pkg"
    assert f.category == Category.UNUSED_DEPENDENCY
    assert f.detection_confidence == "high"
    assert f.confidence == Confidence.SAFE
    assert f.line_start == 12
    assert "Declared in requirements.txt line 12" in f.evidence
    assert "unreferenced-zero-usage-pkg" in f.exact_fix


def test_context_false_positives_explicit(tmp_path: Path):
    """Explicitly verifies the 3 user-reported CONTEXT false positives:

    1. 'python-dotenv' imported as 'from dotenv import load_dotenv'
    2. 'google-genai' imported as 'from google import genai'
    3. 'pytest' referenced in pytest.ini / recognized as test runner tool
    """
    req_file = tmp_path / "requirements.txt"
    req_file.write_text(
        "python-dotenv>=1.0.0\n"
        "google-genai>=0.1.0\n"
        "pytest>=8.0.0\n"
        "unreferenced-pkg==1.0.0\n",
        encoding="utf-8",
    )

    src_file = tmp_path / "main.py"
    src_file.write_text(
        "from dotenv import load_dotenv\n"
        "from google import genai\n"
        "load_dotenv()\n",
        encoding="utf-8",
    )

    pytest_ini = tmp_path / "pytest.ini"
    pytest_ini.write_text("[pytest]\ntestpaths = tests\n", encoding="utf-8")

    auditor = PythonDependencyAuditor(tmp_path, OptiConfig())
    findings = auditor.audit()

    flagged_packages = {f.target_entity for f in findings}
    assert "python-dotenv" not in flagged_packages, "python-dotenv was falsely flagged!"
    assert "google-genai" not in flagged_packages, "google-genai was falsely flagged!"
    assert "pytest" not in flagged_packages, "pytest was falsely flagged!"
    assert "unreferenced-pkg" in flagged_packages, "unreferenced-pkg should have been flagged!"

    unused_finding = next(f for f in findings if f.target_entity == "unreferenced-pkg")
    assert unused_finding.detection_confidence == "high"


def test_pyproject_toml_dependencies_and_optional(tmp_path: Path):
    """Tests scanning pyproject.toml [project.dependencies] and optional-dependencies."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """[project]
name = "demo-project"
version = "0.1.0"
dependencies = [
    "pyyaml>=6.0",
    "dead-prod-pkg>=2.0.0",
]

[project.optional-dependencies]
extra-feature = [
    "optional-unused-pkg>=1.0.0",
]
""",
        encoding="utf-8",
    )

    src = tmp_path / "app.py"
    src.write_text("import yaml\n", encoding="utf-8")

    auditor = PythonDependencyAuditor(tmp_path, OptiConfig())
    findings = auditor.audit()

    flagged = {f.target_entity: f for f in findings}
    assert "pyyaml" not in flagged, "pyyaml should have resolved to yaml and not be flagged!"

    # dead-prod-pkg must be high confidence
    assert "dead-prod-pkg" in flagged
    assert flagged["dead-prod-pkg"].detection_confidence == "high"
    assert flagged["dead-prod-pkg"].confidence == Confidence.SAFE

    # optional-unused-pkg must be low confidence
    assert "optional-unused-pkg" in flagged
    assert flagged["optional-unused-pkg"].detection_confidence == "low"
    assert flagged["optional-unused-pkg"].confidence == Confidence.RISKY


def test_custom_aliases_and_tools_config(tmp_path: Path):
    """Tests custom alias resolution and custom tool declarations in OptiConfig."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text(
        "my-secret-internal-pkg>=1.0.0\n"
        "my-custom-cli-runner>=2.0.0\n",
        encoding="utf-8",
    )

    src = tmp_path / "service.py"
    src.write_text("import internal_module\n", encoding="utf-8")

    config = OptiConfig()
    config.dependencies = DependenciesConfig(
        aliases={"my-secret-internal-pkg": ["internal_module"]},
        tools=["my-custom-cli-runner"],
    )

    # In script / Makefile
    makefile = tmp_path / "Makefile"
    makefile.write_text("run:\n\tmy-custom-cli-runner --fast\n", encoding="utf-8")

    auditor = PythonDependencyAuditor(tmp_path, config)
    findings = auditor.audit()

    assert len(findings) == 0, f"Expected 0 findings with custom aliases and tools, got: {[f.target_entity for f in findings]}"


def test_fix_only_high_detection_confidence_and_rollback(tmp_path: Path):
    """Tests that WasteFinderPlugin.propose_fixes ONLY auto-removes dependencies

    when detection_confidence == 'high', and rollback restores the original manifest.
    """
    req_file = tmp_path / "requirements.txt"
    original_content = (
        "python-dotenv==1.0.1\n"
        "unreferenced-zero-usage-pkg==1.0.0\n"
    )
    req_file.write_text(original_content, encoding="utf-8")

    src = tmp_path / "app.py"
    src.write_text("from dotenv import load_dotenv\nload_dotenv()\n", encoding="utf-8")

    target = Target(kind=TargetKind.CODEBASE, identifier=str(tmp_path), path=tmp_path)
    config = OptiConfig(project_root=tmp_path)

    plugin = WasteFinderPlugin()
    findings = plugin.analyze(target, config)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.target_entity == "unreferenced-zero-usage-pkg"
    assert finding.detection_confidence == "high"

    # Propose fixes
    proposals = plugin.propose_fixes(findings, target, config)
    assert len(proposals) == 1
    prop = proposals[0]

    # Verify a medium confidence finding is NOT proposed for fix
    finding_medium = dataclasses.replace(findings[0], id="OPT-DEP-MED", detection_confidence="medium")
    assert len(plugin.propose_fixes([finding_medium], target, config)) == 0

    # Apply the high confidence fix via SafetyEngine
    safety = SafetyEngine(config=config)
    results = safety.apply_proposals(proposals, target)
    assert len(results) == 1
    assert results[0].success

    # Content after fix
    modified_content = req_file.read_text(encoding="utf-8")
    assert "unreferenced-zero-usage-pkg" not in modified_content
    assert "python-dotenv==1.0.1" in modified_content

    # Rollback operation
    res = safety.rollback()
    assert res["success"] is True
    restored_content = req_file.read_text(encoding="utf-8")
    assert restored_content == original_content


def test_cli_format_json_gatekeeper_schema():
    """Tests that running CLI with --format json outputs machine-readable JSON

    matching Gatekeeper's expected schema.
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(FIXTURE_DIR), "--format", "json"])
    assert result.exit_code == 0

    parsed = json.loads(result.output)
    assert isinstance(parsed, list)
    assert len(parsed) >= 1

    # Locate the unused dependency finding
    dep_findings = [f for f in parsed if f["type"] == Category.UNUSED_DEPENDENCY.value]
    assert len(dep_findings) == 1

    f = dep_findings[0]
    # Verify Gatekeeper required schema fields
    required_keys = {
        "id", "type", "file", "line_start", "line_end", "message",
        "description", "confidence", "detection_confidence", "evidence", "exact_fix"
    }
    for k in required_keys:
        assert k in f, f"Missing key '{k}' in JSON finding output"

    assert f["detection_confidence"] == "high"
    assert f["confidence"] == "Safe"
    assert "unreferenced-zero-usage-pkg" in f["message"]
    assert f["line_start"] == 12
    assert "Declared in requirements.txt line 12" in f["evidence"]
