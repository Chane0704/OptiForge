"""Rich Terminal and CLI Reporting for OptiForge."""

from __future__ import annotations

from typing import Any, Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from optiforge.core.finding import Category, Confidence, Effort, Finding, Impact, FixProposal, FixResult
from optiforge.core.target import Target

console = Console()


def print_banner(target: Target, dry_run: bool = False):
    """Prints the OptiForge header panel."""
    mode_text = "[bold yellow]DRY-RUN (Safe Mode)[/bold yellow]" if dry_run else "[bold green]LIVE EXECUTION[/bold green]"
    title_text = f"[bold cyan]⚡ OptiForge[/bold cyan] [dim]v0.1.0[/dim] — Universal Performance & Efficiency Optimizer"
    details = f"Target: [bold white]{target.identifier}[/bold white] | Kind: [bold magenta]{target.kind.value.upper()}[/bold magenta] | Mode: {mode_text}"
    console.print(Panel(f"{title_text}\n{details}", box=box.ROUNDED, style="cyan"))


def get_impact_badge(impact: Impact) -> Text:
    if impact == Impact.HIGH:
        return Text("HIGH", style="bold red")
    if impact == Impact.MEDIUM:
        return Text("MED", style="yellow")
    return Text("LOW", style="cyan")


def get_confidence_badge(conf: Confidence) -> Text:
    if conf == Confidence.SAFE:
        return Text("SAFE", style="bold green")
    if conf == Confidence.LIKELY:
        return Text("LIKELY", style="blue")
    return Text("RISKY", style="magenta")


def get_effort_badge(effort: Effort) -> Text:
    if effort in (Effort.TRIVIAL, Effort.EASY):
        return Text(effort.value.upper(), style="green")
    if effort == Effort.MODERATE:
        return Text(effort.value.upper(), style="yellow")
    return Text(effort.value.upper(), style="red")


def print_findings_summary(findings: List[Finding]):
    """Renders a structured table of findings."""
    if not findings:
        console.print("\n[bold green]✓ No inefficiencies or performance bottlenecks detected! System is running optimally.[/bold green]\n")
        return

    table = Table(
        title=f"Findings & Optimization Opportunities ({len(findings)} Total)",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=True,
    )

    table.add_column("ID", style="bold white", width=12)
    table.add_column("Category", style="dim", width=18)
    table.add_column("Finding & Impact Summary", style="white", min_width=35)
    table.add_column("Impact", justify="center", width=8)
    table.add_column("Effort", justify="center", width=10)
    table.add_column("Safety", justify="center", width=8)

    for f in findings:
        summary_text = Text()
        summary_text.append(f"{f.title}\n", style="bold white")
        summary_text.append(f"{f.description[:140]}..." if len(f.description) > 140 else f.description, style="dim")
        if f.exact_fix:
            summary_text.append(f"\n💡 Fix: {f.exact_fix[:100]}", style="italic cyan")

        table.add_row(
            f.id,
            f.category.value,
            summary_text,
            get_impact_badge(f.impact),
            get_effort_badge(f.effort),
            get_confidence_badge(f.confidence),
        )

    console.print()
    console.print(table)
    console.print()


def print_recommendations_matrix(findings: List[Finding]):
    """Renders the prioritized Impact vs. Effort recommendations matrix."""
    if not findings:
        return

    from optiforge.core.recommendation import RecommendationsEngine, Quadrant

    ranked = RecommendationsEngine.rank_findings(findings)
    summary = RecommendationsEngine.generate_summary(ranked)

    console.print(Panel(
        f"[bold white]Recommendations Engine Matrix[/bold white] — "
        f"[green]Quick Wins: {summary['quick_wins_count']}[/green] | "
        f"[yellow]Strategic: {summary['strategic_count']}[/yellow] | "
        f"[cyan]Maintenance: {summary['maintenance_count']}[/cyan]",
        box=box.ROUNDED,
        style="blue"
    ))

    # Show top 5 priority actions
    top_table = Table(
        title="Top Recommended Action Items (Ranked by ROI)",
        box=box.ROUNDED,
        header_style="bold green",
        show_lines=True,
    )
    top_table.add_column("Rank", justify="center", width=6)
    top_table.add_column("Score", justify="right", width=8)
    top_table.add_column("Category", style="dim", width=18)
    top_table.add_column("Quadrant", style="bold", width=26)
    top_table.add_column("Action & Exact Fix", style="white")

    for rf in ranked[:6]:
        quad_style = "bold green" if rf.quadrant == Quadrant.QUICK_WIN else ("bold yellow" if rf.quadrant == Quadrant.STRATEGIC else "cyan")
        action_text = Text()
        action_text.append(f"{rf.finding.title}\n", style="bold white")
        if rf.finding.exact_fix:
            action_text.append(f"💡 {rf.finding.exact_fix}", style="italic cyan")

        top_table.add_row(
            f"#{rf.rank}",
            f"{rf.score:.1f}",
            rf.finding.category.value,
            Text(rf.quadrant.value.split("(")[0].strip(), style=quad_style),
            action_text,
        )

    console.print(top_table)
    console.print()


def print_fix_proposals(proposals: List[FixProposal], dry_run: bool = True):
    """Prints proposals for automated fixes."""
    if not proposals:
        console.print("[yellow]No automated fix proposals available for the discovered findings.[/yellow]")
        return

    mode_label = "[yellow]DRY-RUN PREVIEW[/yellow]" if dry_run else "[green]TO BE APPLIED[/green]"
    table = Table(
        title=f"Proposed Optimizations ({len(proposals)}) — {mode_label}",
        box=box.ROUNDED,
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("Finding ID", style="bold white", width=12)
    table.add_column("Action", style="cyan", width=16)
    table.add_column("Target Path", style="dim", min_width=25)
    table.add_column("Estimated Savings", justify="right", width=18)
    table.add_column("Description", style="white")

    total_bytes = 0
    for p in proposals:
        savings_str = f"{p.estimated_savings_bytes / 1024:.1f} KB" if p.estimated_savings_bytes > 0 else "N/A"
        total_bytes += p.estimated_savings_bytes
        table.add_row(
            p.finding_id,
            p.action_type.replace("_", " ").upper(),
            str(p.target_path),
            savings_str,
            p.description,
        )

    console.print(table)
    if total_bytes > 0:
        console.print(f"[bold green]Total Estimated Disk/Bandwidth Savings: {total_bytes / (1024*1024):.2f} MB[/bold green]\n")


def print_fix_results(results: List[FixResult]):
    """Prints the outcomes of applied fixes."""
    table = Table(
        title="Applied Fix Results",
        box=box.ROUNDED,
        header_style="bold green",
        show_lines=True,
    )
    table.add_column("Finding ID", width=12)
    table.add_column("Status", width=10)
    table.add_column("Action", width=16)
    table.add_column("Message")

    for r in results:
        status_text = Text("SUCCESS", style="bold green") if r.success else Text("FAILED", style="bold red")
        table.add_row(
            r.finding_id,
            status_text,
            r.action_type,
            r.message
        )

    console.print(table)
