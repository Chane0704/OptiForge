"""Finding and Fix models for OptiForge."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class Category(str, Enum):
    RESOURCE_LEAK = "ResourceLeak"
    HOT_LOOP = "HotLoop"
    HIGH_IDLE = "HighIdle"
    DEAD_CODE = "DeadCode"
    UNUSED_DEPENDENCY = "UnusedDependency"
    ASSET_BLOAT = "AssetBloat"
    DUPLICATE_FILE = "DuplicateFile"
    RENDER_BLOCKING = "RenderBlocking"
    SLOW_TTFB = "SlowTTFB"
    MISSING_COMPRESSION = "MissingCompression"
    CONFIG_TUNING = "ConfigTuning"
    RUNTIME_SMOOTHNESS = "RuntimeSmoothness"


class Confidence(str, Enum):
    SAFE = "Safe"       # 100% deterministic, zero side effects
    LIKELY = "Likely"   # Strong heuristic, review suggested
    RISKY = "Risky"     # Dynamic runtime behavior might be affected


class Impact(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Effort(str, Enum):
    TRIVIAL = "Trivial"
    EASY = "Easy"
    MODERATE = "Moderate"
    HARD = "Hard"


@dataclass
class Finding:
    """Represents a performance inefficiency or waste finding."""
    id: str
    category: Category
    title: str
    description: str
    impact: Impact
    effort: Effort
    confidence: Confidence
    target_entity: str = ""
    target_path: Optional[Path] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    exact_fix: Optional[str] = None
    suggested_diff: Optional[str] = None
    plugin_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "impact": self.impact.value,
            "effort": self.effort.value,
            "confidence": self.confidence.value,
            "target_entity": self.target_entity,
            "target_path": str(self.target_path) if self.target_path else None,
            "metrics": self.metrics,
            "exact_fix": self.exact_fix,
            "plugin_name": self.plugin_name,
        }


@dataclass
class FixProposal:
    """A concrete proposed modification to fix a finding."""
    finding_id: str
    action_type: str  # quarantine_file | modify_file | replace_file | config_update
    target_path: Path
    description: str
    preview_diff: Optional[str] = None
    estimated_savings_bytes: int = 0
    replacement_content: Optional[str | bytes] = None
    custom_action: Optional[Callable[..., Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "action_type": self.action_type,
            "target_path": str(self.target_path),
            "description": self.description,
            "preview_diff": self.preview_diff,
            "estimated_savings_bytes": self.estimated_savings_bytes,
        }


@dataclass
class FixResult:
    """The result of executing a fix proposal."""
    success: bool
    finding_id: str
    action_type: str
    target_path: Path
    message: str
    backup_path: Optional[Path] = None
    quarantine_path: Optional[Path] = None
    bytes_saved: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "finding_id": self.finding_id,
            "action_type": self.action_type,
            "target_path": str(self.target_path),
            "message": self.message,
            "backup_path": str(self.backup_path) if self.backup_path else None,
            "quarantine_path": str(self.quarantine_path) if self.quarantine_path else None,
            "bytes_saved": self.bytes_saved,
        }
