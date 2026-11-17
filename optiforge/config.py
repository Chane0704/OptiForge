"""Configuration models and parser for OptiForge."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


@dataclass
class GeneralConfig:
    safety_level: str = "safe"  # safe | balanced | aggressive
    default_dry_run: bool = True
    backup_dir: str = ".optiforge/backups"
    quarantine_dir: str = ".optiforge/quarantine"


@dataclass
class ThresholdsConfig:
    cpu_hot_percent: float = 75.0
    cpu_idle_high_percent: float = 15.0
    memory_leak_growth_mb: float = 20.0
    oversized_asset_kb: float = 500.0
    slow_ttfb_ms: float = 600.0
    large_bundle_kb: float = 300.0


@dataclass
class IgnoreConfig:
    paths: List[str] = field(default_factory=lambda: [
        "node_modules/**",
        ".git/**",
        "venv/**",
        ".venv/**",
        "__pycache__/**",
        "dist/**",
        "build/**",
        ".optiforge/**",
        "*.pyc",
    ])
    packages: List[str] = field(default_factory=lambda: [
        "wheel",
        "setuptools",
        "pip",
    ])


@dataclass
class OptiConfig:
    version: str = "1.0"
    general: GeneralConfig = field(default_factory=GeneralConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    ignore: IgnoreConfig = field(default_factory=IgnoreConfig)
    plugins: Dict[str, Any] = field(default_factory=dict)
    project_root: Path = field(default_factory=lambda: Path.cwd())

    @classmethod
    def load(cls, config_path: Optional[Path | str] = None, project_root: Optional[Path | str] = None) -> "OptiConfig":
        root = Path(project_root) if project_root else Path.cwd()
        resolved_path: Optional[Path] = None

        if config_path:
            candidate = Path(config_path)
            if candidate.exists():
                resolved_path = candidate
        else:
            for fname in ["optiforge.yaml", "optiforge.yml", ".optiforge.yaml", ".optiforge.yml"]:
                candidate = root / fname
                if candidate.exists():
                    resolved_path = candidate
                    break

        if not resolved_path or not resolved_path.is_file():
            config = cls(project_root=root)
            return config

        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            gen_data = data.get("general", {})
            thresh_data = data.get("thresholds", {})
            ignore_data = data.get("ignore", {})
            plugins_data = data.get("plugins", {})

            return cls(
                version=str(data.get("version", "1.0")),
                general=GeneralConfig(
                    safety_level=gen_data.get("safety_level", "safe"),
                    default_dry_run=gen_data.get("default_dry_run", True),
                    backup_dir=gen_data.get("backup_dir", ".optiforge/backups"),
                    quarantine_dir=gen_data.get("quarantine_dir", ".optiforge/quarantine"),
                ),
                thresholds=ThresholdsConfig(
                    cpu_hot_percent=float(thresh_data.get("cpu_hot_percent", 75.0)),
                    cpu_idle_high_percent=float(thresh_data.get("cpu_idle_high_percent", 15.0)),
                    memory_leak_growth_mb=float(thresh_data.get("memory_leak_growth_mb", 20.0)),
                    oversized_asset_kb=float(thresh_data.get("oversized_asset_kb", 500.0)),
                    slow_ttfb_ms=float(thresh_data.get("slow_ttfb_ms", 600.0)),
                    large_bundle_kb=float(thresh_data.get("large_bundle_kb", 300.0)),
                ),
                ignore=IgnoreConfig(
                    paths=list(ignore_data.get("paths", [
                        "node_modules/**", ".git/**", "venv/**", ".venv/**",
                        "__pycache__/**", "dist/**", "build/**", ".optiforge/**"
                    ])),
                    packages=list(ignore_data.get("packages", ["wheel", "setuptools", "pip"])),
                ),
                plugins=plugins_data,
                project_root=root,
            )
        except Exception:
            return cls(project_root=root)

    def is_path_ignored(self, relative_path: str) -> bool:
        import fnmatch
        norm_path = relative_path.replace("\\", "/")
        for pattern in self.ignore.paths:
            norm_pattern = pattern.replace("\\", "/")
            if fnmatch.fnmatch(norm_path, norm_pattern) or fnmatch.fnmatch(norm_path, f"**/{norm_pattern}"):
                return True
            parts = norm_path.split("/")
            if any(fnmatch.fnmatch(part, norm_pattern.rstrip("/*")) for part in parts):
                return True
        return False
