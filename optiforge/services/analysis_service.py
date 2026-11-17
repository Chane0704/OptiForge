"""Analysis Service for OptiForge.

Translates technical diagnostics into plain-language summaries, calculates
user-friendly health scores, and structures optimization recommendations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from optiforge.config import OptiConfig
from optiforge.core.finding import Category, Confidence, Effort, Finding, FixProposal, FixResult, Impact
from optiforge.core.recommendation import Quadrant, RecommendationsEngine
from optiforge.core.registry import registry, register_builtin_plugins
from optiforge.core.safety import SafetyEngine
from optiforge.core.target import Target
from optiforge.services.input_detector import DetectedInput

logger = logging.getLogger("optiforge.analysis_service")
register_builtin_plugins()


@dataclass
class FriendlyFinding:
    """A user-friendly presentation card for an inefficiency finding."""
    id: str
    friendly_title: str
    why_it_matters: str
    what_to_do: str
    estimated_gain: str
    safety_badge: str  # "Safe", "Probably safe", "Be careful"
    group: str         # "quick_wins" | "worth_doing" | "optional"
    target_entity: str
    raw_finding: Finding
    advanced_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "friendly_title": self.friendly_title,
            "why_it_matters": self.why_it_matters,
            "what_to_do": self.what_to_do,
            "estimated_gain": self.estimated_gain,
            "safety_badge": self.safety_badge,
            "group": self.group,
            "target_entity": self.target_entity,
            "category": self.raw_finding.category.value,
            "impact": self.raw_finding.impact.value,
            "effort": self.raw_finding.effort.value,
            "confidence": self.raw_finding.confidence.value,
            "exact_fix": self.raw_finding.exact_fix,
            "advanced_details": self.advanced_details,
        }


@dataclass
class FriendlyAnalysisResult:
    """Complete plain-English analysis report for the desktop app and CLI."""
    detected_input: DetectedInput
    health_score: int
    health_label: str
    headline_summary: str
    total_savings_mb: float
    current_size_mb: float
    optimized_size_mb: float
    quick_wins: List[FriendlyFinding] = field(default_factory=list)
    worth_doing: List[FriendlyFinding] = field(default_factory=list)
    optional: List[FriendlyFinding] = field(default_factory=list)
    all_findings: List[Finding] = field(default_factory=list)
    telemetry: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_type": self.detected_input.input_type,
            "friendly_label": self.detected_input.friendly_label,
            "health_score": self.health_score,
            "health_label": self.health_label,
            "headline_summary": self.headline_summary,
            "total_savings_mb": self.total_savings_mb,
            "current_size_mb": self.current_size_mb,
            "optimized_size_mb": self.optimized_size_mb,
            "quick_wins": [f.to_dict() for f in self.quick_wins],
            "worth_doing": [f.to_dict() for f in self.worth_doing],
            "optional": [f.to_dict() for f in self.optional],
            "total_findings_count": len(self.all_findings),
        }


class AnalysisService:
    """Unified service for running performance diagnostics and translating results."""

    @classmethod
    def analyze(
        cls,
        detected_input: DetectedInput,
        config: Optional[OptiConfig] = None
    ) -> FriendlyAnalysisResult:
        """Runs the analysis pipeline and returns a structured, plain-language result."""
        cfg = config or OptiConfig()
        target = detected_input.target

        # Execute plugins via core registry
        findings, telemetry = registry.analyze_target(target, cfg)

        # Compute health score: 100 base minus penalties
        penalty = 0
        for f in findings:
            if f.impact == Impact.HIGH:
                penalty += 12
            elif f.impact == Impact.MEDIUM:
                penalty += 6
            else:
                penalty += 2

        health_score = max(15, min(100, 100 - penalty))

        if health_score >= 90:
            health_label = "Excellent (Clean & Fast)"
        elif health_score >= 75:
            health_label = "Good, Easy Wins Available"
        elif health_score >= 50:
            health_label = "Fair (Needs Optimization)"
        else:
            health_label = "Heavy Bloat Detected"

        # Calculate potential byte savings
        total_savings_bytes = sum(f.metrics.get("bytes_saved", 0) for f in findings)
        total_savings_mb = round(total_savings_bytes / (1024 * 1024), 2)

        est_current_bytes = detected_input.estimated_size_bytes or total_savings_bytes * 1.5
        current_size_mb = round(est_current_bytes / (1024 * 1024), 2)
        optimized_size_mb = max(0.01, round(current_size_mb - total_savings_mb, 2))

        # Build headline summary
        if total_savings_mb >= 0.5:
            headline = f"Your project could be {total_savings_mb:.1f} MB smaller and load noticeably faster!"
        elif any(f.category == Category.RESOURCE_LEAK for f in findings):
            headline = "Memory leak detected that will cause your application to slow down over time."
        elif any(f.category == Category.RENDER_BLOCKING for f in findings):
            headline = "Page loading is delayed by scripts in your header. Adding 'defer' will make it load instantly."
        elif not findings:
            headline = "Great news! Your project is running cleanly with zero detected waste."
        else:
            headline = f"We found {len(findings)} optimizations to streamline your software."

        # Map findings into friendly groups
        quick_wins: List[FriendlyFinding] = []
        worth_doing: List[FriendlyFinding] = []
        optional: List[FriendlyFinding] = []

        ranked_items = RecommendationsEngine.rank_findings(findings)

        for rf in ranked_items:
            f = rf.finding
            friendly_card = cls._translate_to_friendly(f)

            if rf.quadrant == Quadrant.QUICK_WIN:
                friendly_card.group = "quick_wins"
                quick_wins.append(friendly_card)
            elif rf.quadrant == Quadrant.STRATEGIC:
                friendly_card.group = "worth_doing"
                worth_doing.append(friendly_card)
            else:
                friendly_card.group = "optional"
                optional.append(friendly_card)

        return FriendlyAnalysisResult(
            detected_input=detected_input,
            health_score=health_score,
            health_label=health_label,
            headline_summary=headline,
            total_savings_mb=total_savings_mb,
            current_size_mb=current_size_mb,
            optimized_size_mb=optimized_size_mb,
            quick_wins=quick_wins,
            worth_doing=worth_doing,
            optional=optional,
            all_findings=findings,
            telemetry=telemetry,
        )

    @classmethod
    def _translate_to_friendly(cls, f: Finding) -> FriendlyFinding:
        """Translates a raw Finding into a plain-English card."""
        # Safety badge mapping
        if f.confidence == Confidence.SAFE:
            safety = "Safe"
        elif f.confidence == Confidence.LIKELY:
            safety = "Probably safe"
        else:
            safety = "Be careful"

        # Estimated gain text
        bytes_saved = f.metrics.get("bytes_saved", 0)
        if bytes_saved > 1024 * 1024:
            gain = f"Saves ~{bytes_saved / (1024 * 1024):.1f} MB"
        elif bytes_saved > 1024:
            gain = f"Saves ~{bytes_saved / 1024:.0f} KB"
        elif f.category == Category.RENDER_BLOCKING:
            gain = "Faster page load"
        elif f.category == Category.RESOURCE_LEAK:
            gain = "Prevents crashes"
        elif f.category == Category.HOT_LOOP:
            gain = "Cuts CPU waste"
        elif f.category == Category.RUNTIME_SMOOTHNESS:
            gain = "Smoother display"
        else:
            gain = "Cleans up project"

        # Friendly title & explanation translation
        if f.category == Category.ASSET_BLOAT and "Image" in f.title:
            ftitle = f"Uncompressed Picture: '{Path(f.target_entity).name}'"
            why = "This picture is larger than it needs to be, which makes pages load much slower."
            todo = "Convert it to modern WebP format without losing visual clarity."
        elif f.category == Category.UNUSED_DEPENDENCY:
            pkg = f.target_entity
            ftitle = f"Unused Code Library: '{pkg}'"
            why = f"The library '{pkg}' is installed but your project code never actually uses it."
            todo = f"Remove '{pkg}' from your dependency list to speed up builds and downloads."
        elif f.category == Category.DUPLICATE_FILE:
            fname = Path(f.target_entity).name
            ftitle = f"Duplicate Copy of File: '{fname}'"
            why = "You have identical copies of this file stored in multiple places, wasting disk space."
            todo = "Keep one copy and clean up the duplicate copy."
        elif f.category == Category.RENDER_BLOCKING:
            ftitle = "Scripts in Header Delaying Page Display"
            why = "Browsers stop drawing the page until external scripts finish loading."
            todo = "Add the 'defer' keyword to your script tags so the page shows immediately."
        elif f.category == Category.RUNTIME_SMOOTHNESS and "CLS" in f.title:
            ftitle = "Pictures Missing Size Labels (Causes Jumpy Layout)"
            why = "When pictures load without width/height numbers, content jumps around suddenly."
            todo = "Add width and height numbers to your picture tags."
        elif f.category == Category.RUNTIME_SMOOTHNESS and "time.sleep" in f.title:
            ftitle = "Code Freeze Caused by Synchronous Sleep"
            why = "Using time.sleep inside async code freezes the entire server, making other users wait."
            todo = "Use 'await asyncio.sleep()' instead so the server can handle other tasks."
        elif f.category == Category.DEAD_CODE and "CSS" in f.title:
            ftitle = "Unused CSS Design Rules"
            why = "Your stylesheet defines visual styles that no part of your website actually uses."
            todo = "Remove the unused style classes to keep your website styles lean."
        elif f.category == Category.RESOURCE_LEAK:
            ftitle = "Memory Leak in Running Process"
            why = "Memory continuously grows without being released, which can eventually crash the app."
            todo = "Review unbounded caches or unclosed connections."
        else:
            ftitle = f.title
            why = f.description
            todo = f.exact_fix or "Review and optimize this item."

        advanced = {
            "finding_id": f.id,
            "category": f.category.value,
            "target_path": str(f.target_path) if f.target_path else None,
            "target_entity": f.target_entity,
            "metrics": f.metrics,
            "raw_description": f.description,
            "exact_fix": f.exact_fix,
        }

        return FriendlyFinding(
            id=f.id,
            friendly_title=ftitle,
            why_it_matters=why,
            what_to_do=todo,
            estimated_gain=gain,
            safety_badge=safety,
            group="quick_wins",
            target_entity=f.target_entity,
            raw_finding=f,
            advanced_details=advanced,
        )

    @classmethod
    def get_fix_proposals(
        cls,
        target: Target,
        findings: List[Finding],
        config: Optional[OptiConfig] = None
    ) -> List[FixProposal]:
        """Collects concrete fix proposals from plugins."""
        cfg = config or OptiConfig()
        return registry.collect_fix_proposals(findings, target, cfg)

    @classmethod
    def apply_fixes(
        cls,
        target: Target,
        proposals: List[FixProposal],
        config: Optional[OptiConfig] = None
    ) -> List[FixResult]:
        """Applies fixes safely with snapshots and quarantine."""
        cfg = config or OptiConfig()
        safety = SafetyEngine(config=cfg)
        return safety.apply_proposals(proposals, target)

    @classmethod
    def rollback_latest(cls, config: Optional[OptiConfig] = None) -> Dict[str, Any]:
        """Restores pre-fix state from latest snapshot."""
        cfg = config or OptiConfig()
        safety = SafetyEngine(config=cfg)
        return safety.rollback()
