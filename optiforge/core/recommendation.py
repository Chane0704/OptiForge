"""Recommendations Engine: Prioritizes and ranks optimization findings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Tuple

from optiforge.core.finding import Category, Confidence, Effort, Finding, Impact


class Quadrant(str, Enum):
    QUICK_WIN = "Quick Win (High Impact, Low Effort)"
    STRATEGIC = "Strategic Improvement (High Impact, High Effort)"
    MAINTENANCE = "Maintenance / Low Hanging Fruit"
    DEFERRED = "Low Priority / High Effort"


@dataclass
class RankedFinding:
    finding: Finding
    score: float
    quadrant: Quadrant
    rank: int


class RecommendationsEngine:
    """Ranks and groups findings by Impact vs. Effort, computing return-on-investment scores."""

    IMPACT_WEIGHTS = {
        Impact.HIGH: 3.0,
        Impact.MEDIUM: 2.0,
        Impact.LOW: 1.0,
    }

    EFFORT_WEIGHTS = {
        Effort.TRIVIAL: 1.0,
        Effort.EASY: 2.0,
        Effort.MODERATE: 3.5,
        Effort.HARD: 5.0,
    }

    CONFIDENCE_WEIGHTS = {
        Confidence.SAFE: 1.0,
        Confidence.LIKELY: 0.85,
        Confidence.RISKY: 0.65,
    }

    @classmethod
    def calculate_score(cls, finding: Finding) -> float:
        imp = cls.IMPACT_WEIGHTS.get(finding.impact, 1.0)
        eff = cls.EFFORT_WEIGHTS.get(finding.effort, 2.0)
        conf = cls.CONFIDENCE_WEIGHTS.get(finding.confidence, 0.8)
        # Score formula: Higher is better ROI
        raw_roi = (imp * 10.0) / eff
        return round(raw_roi * conf, 2)

    @classmethod
    def assign_quadrant(cls, finding: Finding) -> Quadrant:
        is_high_impact = finding.impact in (Impact.HIGH, Impact.MEDIUM)
        is_low_effort = finding.effort in (Effort.TRIVIAL, Effort.EASY)

        if is_high_impact and is_low_effort:
            return Quadrant.QUICK_WIN
        elif is_high_impact and not is_low_effort:
            return Quadrant.STRATEGIC
        elif not is_high_impact and is_low_effort:
            return Quadrant.MAINTENANCE
        else:
            return Quadrant.DEFERRED

    @classmethod
    def rank_findings(cls, findings: List[Finding]) -> List[RankedFinding]:
        scored: List[Tuple[Finding, float, Quadrant]] = []
        for f in findings:
            score = cls.calculate_score(f)
            quadrant = cls.assign_quadrant(f)
            scored.append((f, score, quadrant))

        # Sort descending by score
        scored.sort(key=lambda x: x[1], reverse=True)

        ranked: List[RankedFinding] = []
        for idx, (f, score, quadrant) in enumerate(scored, 1):
            ranked.append(RankedFinding(
                finding=f,
                score=score,
                quadrant=quadrant,
                rank=idx,
            ))

        return ranked

    @classmethod
    def generate_summary(cls, ranked_findings: List[RankedFinding]) -> Dict[str, Any]:
        """Produces an executive synthesis of all recommendations."""
        quick_wins = [rf for rf in ranked_findings if rf.quadrant == Quadrant.QUICK_WIN]
        strategic = [rf for rf in ranked_findings if rf.quadrant == Quadrant.STRATEGIC]
        maintenance = [rf for rf in ranked_findings if rf.quadrant == Quadrant.MAINTENANCE]

        top_leverage = ranked_findings[0] if ranked_findings else None

        return {
            "total_findings": len(ranked_findings),
            "quick_wins_count": len(quick_wins),
            "strategic_count": len(strategic),
            "maintenance_count": len(maintenance),
            "top_recommendation": {
                "id": top_leverage.finding.id,
                "title": top_leverage.finding.title,
                "score": top_leverage.score,
                "exact_fix": top_leverage.finding.exact_fix,
            } if top_leverage else None,
        }
