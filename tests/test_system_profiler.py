"""Tests for SystemProfilerPlugin."""

import os
import pytest
from optiforge.config import OptiConfig
from optiforge.core.target import Target, TargetKind
from optiforge.plugins.system_profiler import SystemProfilerPlugin


def test_system_profiler_can_handle():
    plugin = SystemProfilerPlugin()
    assert plugin.can_handle(Target(kind=TargetKind.PROCESS, identifier="1234", pid=1234))
    assert plugin.can_handle(Target(kind=TargetKind.SYSTEM, identifier="system"))
    assert not plugin.can_handle(Target(kind=TargetKind.WEBSITE, identifier="https://example.com"))


def test_process_profiler_current_process():
    plugin = SystemProfilerPlugin()
    current_pid = os.getpid()
    target = Target(kind=TargetKind.PROCESS, identifier=str(current_pid), pid=current_pid)

    config = OptiConfig()
    config.plugins["system_profiler"] = {
        "sampling_duration_sec": 0.5,
        "sampling_interval_sec": 0.1,
    }

    findings = plugin.analyze(target, config)
    assert isinstance(findings, list)
    # Check that metadata was populated
    assert "pid" in target.metadata
    assert target.metadata["pid"] == current_pid
    assert "rss_mb" in target.metadata


def test_system_profiler_machine_resources():
    plugin = SystemProfilerPlugin()
    target = Target(kind=TargetKind.SYSTEM, identifier="system")
    config = OptiConfig()
    findings = plugin.analyze(target, config)
    assert isinstance(findings, list)
