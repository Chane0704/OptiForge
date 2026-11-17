"""Tests for RecommendationsEngine, SafetyEngine, Quarantine, and Rollback."""

import hashlib
import json
import shutil
from pathlib import Path
import pytest
from PIL import Image

from optiforge.config import OptiConfig
from optiforge.core.finding import Category, Confidence, Effort, Finding, FixProposal, Impact
from optiforge.core.recommendation import Quadrant, RecommendationsEngine
from optiforge.core.safety import SafetyEngine
from optiforge.core.target import Target, TargetKind


def test_recommendations_ranking():
    f_high_trivial = Finding(
        id="F1",
        category=Category.ASSET_BLOAT,
        title="Quick Win Image",
        description="High impact trivial effort",
        impact=Impact.HIGH,
        effort=Effort.TRIVIAL,
        confidence=Confidence.SAFE,
    )
    f_low_hard = Finding(
        id="F2",
        category=Category.CONFIG_TUNING,
        title="Low Priority",
        description="Low impact hard effort",
        impact=Impact.LOW,
        effort=Effort.HARD,
        confidence=Confidence.LIKELY,
    )

    ranked = RecommendationsEngine.rank_findings([f_low_hard, f_high_trivial])
    assert ranked[0].finding.id == "F1"
    assert ranked[0].quadrant == Quadrant.QUICK_WIN
    assert ranked[1].finding.id == "F2"
    assert ranked[1].quadrant == Quadrant.DEFERRED


def test_safety_snapshot_quarantine_and_rollback(tmp_path):
    # Setup temporary test workspace
    workspace = tmp_path / "test_workspace"
    workspace.mkdir()

    file_to_quarantine = workspace / "duplicate.txt"
    file_to_quarantine.write_text("Hello duplicate data 12345", encoding="utf-8")
    original_hash = hashlib.sha256(file_to_quarantine.read_bytes()).hexdigest()

    file_to_modify = workspace / "style.css"
    file_to_modify.write_text("body { color : red ; }", encoding="utf-8")
    mod_original_hash = hashlib.sha256(file_to_modify.read_bytes()).hexdigest()

    config = OptiConfig(project_root=workspace)
    safety = SafetyEngine(config=config)
    target = Target(kind=TargetKind.CODEBASE, identifier=str(workspace), path=workspace)

    proposals = [
        FixProposal(
            finding_id="OPT-DUP-001",
            action_type="quarantine_file",
            target_path=file_to_quarantine,
            description="Quarantine duplicate.txt",
            estimated_savings_bytes=len("Hello duplicate data 12345"),
        ),
        FixProposal(
            finding_id="OPT-MIN-001",
            action_type="modify_file",
            target_path=file_to_modify,
            description="Minify style.css",
            replacement_content="body{color:red}",
        ),
    ]

    # 1. Apply proposals
    results = safety.apply_proposals(proposals, target)
    assert len(results) == 2
    assert all(r.success for r in results)

    # Verify original file_to_quarantine was moved (never deleted directly, exists in quarantine)
    assert not file_to_quarantine.exists()
    assert results[0].quarantine_path.exists()
    assert results[0].quarantine_path.read_text(encoding="utf-8") == "Hello duplicate data 12345"

    # Verify file_to_modify was modified
    assert file_to_modify.read_text(encoding="utf-8") == "body{color:red}"

    # 2. Rollback
    rollback_res = safety.rollback()
    assert rollback_res["success"] is True
    assert rollback_res["restored_count"] == 2
    assert rollback_res["verified_count"] == 2

    # Verify both files are bit-for-bit restored
    assert file_to_quarantine.exists()
    assert hashlib.sha256(file_to_quarantine.read_bytes()).hexdigest() == original_hash
    assert file_to_modify.exists()
    assert hashlib.sha256(file_to_modify.read_bytes()).hexdigest() == mod_original_hash
