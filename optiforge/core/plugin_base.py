"""Base classes and interfaces for OptiForge plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from optiforge.config import OptiConfig
from optiforge.core.finding import Finding, FixProposal
from optiforge.core.target import Target, TargetKind


class BasePlugin(ABC):
    """Abstract base class for all OptiForge plugins."""

    name: str = "base_plugin"
    description: str = "Base plugin interface"
    target_kinds: List[TargetKind] = []

    def __init__(self, config: Optional[OptiConfig] = None):
        self.config = config or OptiConfig()

    @abstractmethod
    def can_handle(self, target: Target) -> bool:
        """Return True if this plugin can analyze or optimize the given target."""
        ...

    @abstractmethod
    def analyze(self, target: Target, config: OptiConfig) -> List[Finding]:
        """Execute analysis on target and return findings."""
        ...

    def propose_fixes(self, findings: List[Finding], target: Target, config: OptiConfig) -> List[FixProposal]:
        """Propose safe, actionable fixes for the identified findings."""
        return []


class AnalyzerPlugin(BasePlugin):
    """Specialized plugin focused purely on diagnostics and profiling."""
    pass


class OptimizerPlugin(BasePlugin):
    """Specialized plugin that analyzes and provides automated optimizations."""
    pass
