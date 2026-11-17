"""Plugin registry and lifecycle management for OptiForge."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Type
from optiforge.config import OptiConfig
from optiforge.core.finding import Finding, FixProposal
from optiforge.core.plugin_base import BasePlugin
from optiforge.core.target import Target

logger = logging.getLogger("optiforge.registry")


class PluginRegistry:
    """Central registry and executor for OptiForge plugins."""

    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin) -> None:
        """Register an instantiated plugin instance."""
        self._plugins[plugin.name] = plugin
        logger.debug(f"Registered plugin: {plugin.name}")

    def unregister(self, name: str) -> None:
        """Unregister a plugin by name."""
        if name in self._plugins:
            del self._plugins[name]

    def get(self, name: str) -> Optional[BasePlugin]:
        return self._plugins.get(name)

    def list_plugins(self) -> List[BasePlugin]:
        return list(self._plugins.values())

    def get_plugins_for_target(self, target: Target, config: OptiConfig) -> List[BasePlugin]:
        """Return all enabled plugins capable of handling the target."""
        eligible = []
        for name, plugin in self._plugins.items():
            plugin_cfg = config.plugins.get(name, {})
            if isinstance(plugin_cfg, dict) and not plugin_cfg.get("enabled", True):
                continue
            if plugin.can_handle(target):
                eligible.append(plugin)
        return eligible

    def analyze_target(
        self,
        target: Target,
        config: OptiConfig
    ) -> Tuple[List[Finding], Dict[str, Any]]:
        """Run all matching plugins against target and aggregate findings and telemetry."""
        findings: List[Finding] = []
        telemetry: Dict[str, Any] = {
            "target": target.identifier,
            "target_kind": target.kind.value,
            "plugins_run": [],
            "metrics": {},
        }

        eligible_plugins = self.get_plugins_for_target(target, config)
        for plugin in eligible_plugins:
            try:
                plugin_findings = plugin.analyze(target, config)
                findings.extend(plugin_findings)
                telemetry["plugins_run"].append(plugin.name)
            except Exception as e:
                logger.error(f"Error running plugin {plugin.name}: {e}", exc_info=True)
                telemetry["plugins_run"].append(f"{plugin.name} (failed: {e})")

        return findings, telemetry

    def collect_fix_proposals(
        self,
        findings: List[Finding],
        target: Target,
        config: OptiConfig
    ) -> List[FixProposal]:
        """Collect all fix proposals from capable plugins for given findings."""
        proposals: List[FixProposal] = []
        eligible_plugins = self.get_plugins_for_target(target, config)

        for plugin in eligible_plugins:
            try:
                plugin_proposals = plugin.propose_fixes(findings, target, config)
                proposals.extend(plugin_proposals)
            except Exception as e:
                logger.error(f"Error collecting fixes from {plugin.name}: {e}", exc_info=True)

        return proposals


# Global default registry instance
registry = PluginRegistry()


def register_builtin_plugins():
    """Dynamically register all builtin plugins."""
    try:
        from optiforge.plugins.system_profiler import SystemProfilerPlugin
        registry.register(SystemProfilerPlugin())
    except ImportError as e:
        logger.warning(f"Could not load SystemProfilerPlugin: {e}")

    # Builtin plugins for subsequent phases will register cleanly when implemented
    try:
        from optiforge.plugins.website_analyzer import WebsiteAnalyzerPlugin
        registry.register(WebsiteAnalyzerPlugin())
    except ImportError:
        pass

    try:
        from optiforge.plugins.compressor import CompressorPlugin
        registry.register(CompressorPlugin())
    except ImportError:
        pass

    try:
        from optiforge.plugins.waste_finder import WasteFinderPlugin
        registry.register(WasteFinderPlugin())
    except ImportError:
        pass

    try:
        from optiforge.plugins.runtime_tuner import RuntimeTunerPlugin
        registry.register(RuntimeTunerPlugin())
    except ImportError:
        pass
