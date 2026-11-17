"""Tests for RuntimeTunerPlugin."""

from pathlib import Path
import pytest
from optiforge.config import OptiConfig
from optiforge.core.finding import Category
from optiforge.core.target import Target, TargetKind
from optiforge.plugins.runtime_tuner import RuntimeTunerPlugin


def test_runtime_tuner_async_blocking():
    plugin = RuntimeTunerPlugin()
    target = Target(
        kind=TargetKind.CODEBASE,
        identifier="sample_bloated_project",
        path=Path("sample_bloated_project"),
    )
    config = OptiConfig()
    findings = plugin.analyze(target, config)

    # Should detect blocking time.sleep inside async def in src/api.py
    async_blocks = [f for f in findings if "time.sleep" in f.title]
    assert len(async_blocks) >= 1
    assert "handle_request_async" in async_blocks[0].title
