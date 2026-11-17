"""Tests for OptiForge core models, target detection, and configuration."""

from pathlib import Path
import pytest
from optiforge.config import OptiConfig
from optiforge.core.finding import Category, Confidence, Effort, Finding, Impact
from optiforge.core.registry import PluginRegistry
from optiforge.core.target import Target, TargetKind


def test_target_detection():
    # Website
    t_web = Target.from_string("https://example.com/api")
    assert t_web.kind == TargetKind.WEBSITE
    assert t_web.url == "https://example.com/api"

    # Process by PID
    t_proc_pid = Target.from_string("12345")
    assert t_proc_pid.kind == TargetKind.PROCESS
    assert t_proc_pid.pid == 12345

    # Process by name prefix
    t_proc_name = Target.from_string("proc:python")
    assert t_proc_name.kind == TargetKind.PROCESS
    assert t_proc_name.process_name == "python"

    # System
    t_sys = Target.from_string("system")
    assert t_sys.kind == TargetKind.SYSTEM

    # Codebase
    t_code = Target.from_string(".")
    assert t_code.kind == TargetKind.CODEBASE
    assert t_code.path is not None


def test_finding_serialization():
    finding = Finding(
        id="OPT-TEST-001",
        category=Category.RESOURCE_LEAK,
        title="Test Leak",
        description="A test leak finding",
        impact=Impact.HIGH,
        effort=Effort.EASY,
        confidence=Confidence.SAFE,
        metrics={"leaked_bytes": 1024},
        exact_fix="Close the leak",
    )
    d = finding.to_dict()
    assert d["id"] == "OPT-TEST-001"
    assert d["category"] == "ResourceLeak"
    assert d["impact"] == "High"
    assert d["effort"] == "Easy"
    assert d["confidence"] == "Safe"


def test_config_ignore_paths():
    config = OptiConfig()
    assert config.is_path_ignored("node_modules/express/index.js")
    assert config.is_path_ignored(".git/config")
    assert config.is_path_ignored(".optiforge/backups/manifest.json")
    assert not config.is_path_ignored("src/app.py")
