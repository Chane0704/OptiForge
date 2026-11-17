"""Analysis Service for OptiForge.

Translates technical diagnostics into plain-language summaries, calculates
user-friendly health scores using real documented formulas, and structures
optimization recommendations without fake or placeholder values.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from optiforge.config import OptiConfig
from optiforge.core.finding import Category, Confidence, Effort, Finding, FixProposal, FixResult, Impact
from optiforge.core.recommendation import Quadrant, RecommendationsEngine
from optiforge.core.registry import registry, register_builtin_plugins
from optiforge.core.safety import SafetyEngine
from optiforge.core.target import Target, TargetKind
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
    gain_type: str = "estimated"       # "measured" | "estimated" | "varies"
    safety_badge: str = "Probably safe"    # "Safe", "Probably safe", "Be careful"
    group: str = "quick_wins"           # "quick_wins" | "worth_doing" | "optional"
    target_entity: str = ""
    file_path: str = ""
    line_number: Optional[int] = None
    raw_finding: Optional[Finding] = None
    advanced_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        category_val = self.raw_finding.category.value if self.raw_finding else "efficiency"
        impact_val = self.raw_finding.impact.value if self.raw_finding else "medium"
        effort_val = self.raw_finding.effort.value if self.raw_finding else "low"
        confidence_val = self.raw_finding.confidence.value if self.raw_finding else "safe"
        exact_fix_val = self.raw_finding.exact_fix if self.raw_finding else ""
        return {
            "id": self.id,
            "friendly_title": self.friendly_title,
            "plain_title": self.friendly_title,
            "why_it_matters": self.why_it_matters,
            "what_to_do": self.what_to_do,
            "estimated_gain": self.estimated_gain,
            "gain_type": self.gain_type,
            "safety_badge": self.safety_badge,
            "group": self.group,
            "target_entity": self.target_entity,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "category": category_val,
            "impact": impact_val,
            "effort": effort_val,
            "confidence": confidence_val,
            "exact_fix": exact_fix_val,
            "advanced_details": self.advanced_details,
        }


@dataclass
class FriendlyAnalysisResult:
    """Complete plain-English analysis report for the desktop app and CLI."""
    detected_input: DetectedInput
    health_score: int
    health_score_formula: str
    health_label: str
    headline_summary: str
    total_savings_mb: float
    current_size_mb: float
    optimized_size_mb: float
    estimated_speed_gain: str
    speed_gain_type: str
    target_name: str
    target_path: str
    item_count: int
    tech_stack: str
    analyzed_at: str
    quick_wins: List[FriendlyFinding] = field(default_factory=list)
    worth_doing: List[FriendlyFinding] = field(default_factory=list)
    optional: List[FriendlyFinding] = field(default_factory=list)
    all_findings: List[Finding] = field(default_factory=list)
    telemetry: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        safe_fixes_count = sum(1 for f in self.quick_wins + self.worth_doing if f.safety_badge == "Safe")
        return {
            "input_type": self.detected_input.input_type,
            "friendly_label": self.target_name,
            "target_name": self.target_name,
            "target_path": self.target_path,
            "item_count": self.item_count,
            "tech_stack": self.tech_stack,
            "analyzed_at": self.analyzed_at,
            "health_score": self.health_score,
            "health_score_formula": self.health_score_formula,
            "health_label": self.health_label,
            "headline_summary": self.headline_summary,
            "total_savings_mb": self.total_savings_mb,
            "current_size_mb": self.current_size_mb,
            "optimized_size_mb": self.optimized_size_mb,
            "estimated_speed_gain": self.estimated_speed_gain,
            "speed_gain_type": self.speed_gain_type,
            "speed_gain_source": self.speed_gain_type,
            "safe_fixes_count": safe_fixes_count,
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

        # 1. Compute health score: Real documented formula based on finding impacts
        # Base = 100
        # High impact: -12 pts
        # Medium impact: -6 pts
        # Low impact: -2 pts
        high_count = sum(1 for f in findings if f.impact == Impact.HIGH)
        med_count = sum(1 for f in findings if f.impact == Impact.MEDIUM)
        low_count = sum(1 for f in findings if f.impact == Impact.LOW)
        penalty = (high_count * 12) + (med_count * 6) + (low_count * 2)

        health_score = max(10, min(100, 100 - penalty))

        formula_desc = (
            f"Base score: 100. Deductions: {penalty} pts total "
            f"({high_count} High @ -12, {med_count} Med @ -6, {low_count} Low @ -2)."
        )

        if health_score >= 95:
            health_label = "Optimal (Clean & Efficient)"
        elif health_score >= 80:
            health_label = "Good, Easy Wins Available"
        elif health_score >= 50:
            health_label = "Fair (Noticeable Inefficiencies)"
        else:
            health_label = "Heavy Bloat Detected"

        # 2. Calculate potential byte savings from real measured metrics
        total_savings_bytes = sum(f.metrics.get("bytes_saved", 0) or f.metrics.get("wasted_bytes", 0) for f in findings)
        total_savings_mb = round(total_savings_bytes / (1024 * 1024), 2)

        # 3. Calculate real project size on disk
        real_current_bytes = detected_input.estimated_size_bytes
        if real_current_bytes == 0 and target.path and target.path.exists():
            if target.path.is_file():
                real_current_bytes = target.path.stat().st_size
            else:
                real_current_bytes = sum(f.stat().st_size for f in target.path.rglob("*") if f.is_file())

        current_size_mb = round(real_current_bytes / (1024 * 1024), 2) if real_current_bytes else 0.0
        optimized_size_mb = max(0.0, round(current_size_mb - total_savings_mb, 2))

        # 4. Calculate real speed gain (NO FAKE HARDCODED DEFAULTS)
        # Sum measured latency reductions or parser delay from findings
        measured_speed_ms = 0.0
        for f in findings:
            if "time_saved_ms" in f.metrics:
                measured_speed_ms += f.metrics["time_saved_ms"]
            elif "ttfb_reduction_ms" in f.metrics:
                measured_speed_ms += f.metrics["ttfb_reduction_ms"]
            elif f.category == Category.RENDER_BLOCKING:
                # Industry standard heuristic: external blocking scripts in head delay DOM parser by ~150-250ms
                blocking_count = f.metrics.get("blocking_scripts_count", 1)
                measured_speed_ms += blocking_count * 200

        if measured_speed_ms > 0:
            estimated_speed_gain = f"~{int(measured_speed_ms)} ms"
            speed_gain_type = "estimated"
        elif not findings:
            estimated_speed_gain = "Optimal"
            speed_gain_type = "measured"
        elif target.kind == TargetKind.CODEBASE:
            estimated_speed_gain = "0 ms"
            speed_gain_type = "measured"
        else:
            estimated_speed_gain = "Impact varies"
            speed_gain_type = "varies"

        # 5. Build headline summary
        if total_savings_mb >= 0.1:
            headline = f"Your project could be {total_savings_mb:.2f} MB smaller."
        elif any(f.category == Category.RESOURCE_LEAK for f in findings):
            headline = "Memory leak detected that degrades system performance over time."
        elif any(f.category == Category.RENDER_BLOCKING for f in findings):
            headline = "Page display is delayed by synchronous header scripts. Adding 'defer' resolves it."
        elif not findings:
            headline = "Your project is clean. No bloat, dead code, or waste detected."
        else:
            headline = f"Found {len(findings)} optimization opportunities to streamline your software."

        # 6. Map findings into friendly groups
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

        # Target metadata resolution
        target_name = detected_input.friendly_label
        target_path = detected_input.target_path or str(target.path or target.url or target.identifier)
        item_count = detected_input.item_count
        tech_stack = detected_input.language or ", ".join(detected_input.detected_tech_stack) or "General"
        analyzed_at = datetime.datetime.now().strftime("%b %d, %Y at %I:%M %p")

        return FriendlyAnalysisResult(
            detected_input=detected_input,
            health_score=health_score,
            health_score_formula=formula_desc,
            health_label=health_label,
            headline_summary=headline,
            total_savings_mb=total_savings_mb,
            current_size_mb=current_size_mb,
            optimized_size_mb=optimized_size_mb,
            estimated_speed_gain=estimated_speed_gain,
            speed_gain_type=speed_gain_type,
            target_name=target_name,
            target_path=target_path,
            item_count=item_count,
            tech_stack=tech_stack,
            analyzed_at=analyzed_at,
            quick_wins=quick_wins,
            worth_doing=worth_doing,
            optional=optional,
            all_findings=findings,
            telemetry=telemetry,
        )

    @classmethod
    def _translate_to_friendly(cls, f: Finding) -> FriendlyFinding:
        """Translates a raw Finding into a plain-English card with measured vs estimated clarity."""
        # Safety badge mapping
        if f.confidence == Confidence.SAFE:
            safety = "Safe"
        elif f.confidence == Confidence.LIKELY:
            safety = "Probably safe"
        else:
            safety = "Be careful"

        # Determine exact byte or time gain
        bytes_saved = f.metrics.get("bytes_saved", 0) or f.metrics.get("wasted_bytes", 0)
        time_saved = f.metrics.get("time_saved_ms", 0) or f.metrics.get("ttfb_reduction_ms", 0)

        if bytes_saved > 1024 * 1024:
            gain = f"Saves {bytes_saved / (1024 * 1024):.2f} MB"
            gain_type = "measured"
        elif bytes_saved > 0:
            gain = f"Saves {bytes_saved / 1024:.1f} KB"
            gain_type = "measured"
        elif time_saved > 0:
            gain = f"Saves ~{time_saved:.0f} ms"
            gain_type = "estimated"
        elif f.category == Category.RENDER_BLOCKING:
            gain = "Faster initial paint"
            gain_type = "estimated"
        elif f.category == Category.RESOURCE_LEAK:
            gain = "Prevents memory leak"
            gain_type = "measured"
        elif f.category == Category.HOT_LOOP:
            gain = "Reduces CPU usage"
            gain_type = "estimated"
        else:
            gain = "Impact varies"
            gain_type = "varies"

        # File path & Line number
        file_path_str = str(f.target_path) if f.target_path else f.target_entity
        line_num = f.metrics.get("line_number") or f.metrics.get("lineno")

        # Friendly title & explanation translation
        if f.category == Category.ASSET_BLOAT and ("Image" in f.title or "Uncompressed" in f.title):
            fname = Path(f.target_entity).name
            ftitle = f"Uncompressed Image: '{fname}'"
            why = "This image is in an uncompressed legacy format, increasing storage and load times."
            todo = "Re-encode to modern WebP format without visible quality loss."
        elif f.category == Category.UNUSED_DEPENDENCY:
            pkg = f.target_entity
            ftitle = f"Unused Dependency: '{pkg}'"
            why = f"The package '{pkg}' is listed in your manifest, but no source file imports it."
            todo = f"Uninstall or remove '{pkg}' from your manifest to reduce install size."
        elif f.category == Category.DUPLICATE_FILE:
            fname = Path(f.target_entity).name
            ftitle = f"Duplicate Copy: '{fname}'"
            why = "Identical duplicate copy found on disk with identical cryptographic SHA-256 hash."
            todo = "Quarantine redundant copy and reference the canonical asset."
        elif f.category == Category.RENDER_BLOCKING:
            ftitle = "Render-Blocking Script in <head>"
            why = "Synchronous scripts in the HTML header block the browser from drawing the page."
            todo = "Add the 'defer' or 'async' attribute so the page renders immediately."
        elif f.category == Category.DEAD_CODE:
            ftitle = f"Dead Code: '{f.target_entity}'"
            why = "Function or block defined but unreferenced across project AST."
            todo = "Safely prune or archive unused dead code."
        else:
            ftitle = f.title
            why = f.description
            todo = f.exact_fix or "Review and optimize this component."

        return FriendlyFinding(
            id=f.id,
            friendly_title=ftitle,
            why_it_matters=why,
            what_to_do=todo,
            estimated_gain=gain,
            gain_type=gain_type,
            safety_badge=safety,
            group="optional",
            target_entity=f.target_entity,
            file_path=file_path_str,
            line_number=line_num,
            raw_finding=f,
            advanced_details={"finding_id": f.id, **f.metrics},
        )

    @classmethod
    def get_fix_proposals(
        cls,
        target: Target,
        findings: List[Finding],
        config: Optional[OptiConfig] = None
    ) -> List[FixProposal]:
        """Gathers safe fix proposals from core plugins."""
        cfg = config or OptiConfig()
        return registry.collect_fix_proposals(findings, target, cfg)

    @classmethod
    def apply_fixes(
        cls,
        target: Target,
        proposals: List[FixProposal],
        config: Optional[OptiConfig] = None
    ) -> List[FixResult]:
        """Applies chosen fixes through the atomic safety engine."""
        cfg = config or OptiConfig()
        safety = SafetyEngine(cfg)
        return safety.apply_proposals(proposals, target)

    @classmethod
    def rollback_latest(cls, config: Optional[OptiConfig] = None, snapshot_id: Optional[str] = None) -> Dict[str, Any]:
        """Reverts modifications from a snapshot."""
        cfg = config or OptiConfig()
        safety = SafetyEngine(cfg)
        return safety.rollback(snapshot_id)
