"""Markdown Report Generator for OptiForge."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict, List

from optiforge.core.finding import Finding
from optiforge.core.recommendation import RecommendationsEngine
from optiforge.core.target import Target


def export_markdown_report(
    target: Target,
    findings: List[Finding],
    telemetry: Dict[str, Any],
    output_path: str | Path,
) -> Path:
    """Generates and writes a comprehensive Markdown performance audit report."""
    ranked = RecommendationsEngine.rank_findings(findings)
    summary = RecommendationsEngine.generate_summary(ranked)
    total_savings_bytes = sum(f.metrics.get("bytes_saved", 0) for f in findings)
    total_savings_mb = total_savings_bytes / (1024 * 1024)

    lines: List[str] = [
        f"# OptiForge Performance & Optimization Report",
        f"",
        f"> **Generated At:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"> **Target:** `{target.identifier}` ({target.kind.value.upper()})  ",
        f"> **Total Findings:** {len(findings)} | **Estimated Disk/Payload Savings:** {total_savings_mb:.2f} MB",
        f"",
        f"---",
        f"",
        f"## 1. Executive Summary",
        f"",
        f"| Metric | Value |",
        f"| :--- | :--- |",
        f"| **Target Entity** | `{target.identifier}` |",
        f"| **Target Kind** | `{target.kind.value}` |",
        f"| **Total Inefficiencies Detected** | {len(findings)} |",
        f"| **Quick Wins (High ROI)** | {summary['quick_wins_count']} |",
        f"| **Strategic Refactors** | {summary['strategic_count']} |",
        f"| **Maintenance / Low-Hanging Fruit** | {summary['maintenance_count']} |",
        f"| **Potential Storage/Bandwidth Savings** | **{total_savings_mb:.2f} MB** |",
        f"",
        f"---",
        f"",
        f"## 2. Prioritized Action Backlog (Ranked by ROI)",
        f"",
        f"| Rank | ID | Category | Quadrant | Title | Impact | Effort | Confidence |",
        f"| :---: | :--- | :--- | :--- | :--- | :---: | :---: | :---: |",
    ]

    for rf in ranked:
        f = rf.finding
        quad_label = rf.quadrant.value.split("(")[0].strip()
        lines.append(
            f"| #{rf.rank} | `{f.id}` | {f.category.value} | {quad_label} | {f.title} | {f.impact.value} | {f.effort.value} | {f.confidence.value} |"
        )

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 3. Detailed Findings & Exact Fix Instructions",
        f"",
    ])

    for rf in ranked:
        f = rf.finding
        lines.extend([
            f"### `{f.id}`: {f.title}",
            f"- **Category:** {f.category.value} | **Confidence:** {f.confidence.value}",
            f"- **Target Entity:** `{f.target_entity or (f.target_path if f.target_path else 'Global')}`",
            f"- **Description:** {f.description}",
        ])
        if f.exact_fix:
            lines.extend([
                f"- **Exact Fix:**",
                f"  ```text",
                f"  {f.exact_fix}",
                f"  ```",
            ])
        lines.append("")

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines), encoding="utf-8")
    return out_file
