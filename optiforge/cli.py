"""Main Command Line Interface for OptiForge."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional
import click
from rich.console import Console

from optiforge.config import OptiConfig
from optiforge.core.registry import registry, register_builtin_plugins
from optiforge.core.target import Target, TargetKind
from optiforge.reporting.cli_reporter import (
    console,
    print_banner,
    print_findings_summary,
    print_recommendations_matrix,
    print_fix_proposals,
    print_fix_results,
)

# Ensure built-in plugins are registered
register_builtin_plugins()


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(version="0.1.0", prog_name="OptiForge")
def cli():
    """⚡ OptiForge: Universal performance and efficiency optimizer."""
    pass


@cli.command("analyze")
@click.argument("target_input", required=False, default=".")
@click.option("-c", "--config", "config_file", type=click.Path(exists=True), help="Path to optiforge.yaml")
@click.option("-d", "--duration", type=float, default=None, help="Process/System sampling duration in seconds")
@click.option("--export-json", type=click.Path(), help="Export findings to a JSON file")
@click.option("--export-md", type=click.Path(), help="Export findings to a Markdown file")
@click.option("--export-html", type=click.Path(), help="Export findings to a standalone interactive HTML dashboard")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose diagnostic logging")
def analyze(
    target_input: str,
    config_file: Optional[str],
    duration: Optional[float],
    export_json: Optional[str],
    export_md: Optional[str],
    export_html: Optional[str],
    verbose: bool,
):
    """Analyze a software target (website URL, process ID/name, codebase directory, or 'system')."""
    config = OptiConfig.load(config_path=config_file)
    if duration is not None:
        if "system_profiler" not in config.plugins:
            config.plugins["system_profiler"] = {}
        config.plugins["system_profiler"]["sampling_duration_sec"] = duration

    from optiforge.services.input_detector import InputDetector
    detected = InputDetector.detect(target_input)
    target = detected.target
    print_banner(target, dry_run=True)

    with console.status(f"[cyan]Analyzing target '{target.identifier}' with active plugins...[/cyan]", spinner="dots"):
        findings, telemetry = registry.analyze_target(target, config)

    print_findings_summary(findings)
    print_recommendations_matrix(findings)

    # Optional exports
    if export_json:
        try:
            import json
            out_data = {
                "telemetry": telemetry,
                "findings": [f.to_dict() for f in findings],
            }
            with open(export_json, "w", encoding="utf-8") as f:
                json.dump(out_data, f, indent=2)
            console.print(f"[green]✓ Exported JSON report to {export_json}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to export JSON report: {e}[/red]")

    if export_md:
        try:
            from optiforge.reporting.markdown_reporter import export_markdown_report
            export_markdown_report(target, findings, telemetry, export_md)
            console.print(f"[green]✓ Exported Markdown report to {export_md}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to export Markdown report: {e}[/red]")

    if export_html:
        try:
            from optiforge.reporting.dashboard_server import export_standalone_dashboard
            export_standalone_dashboard(target, findings, telemetry, export_html)
            console.print(f"[green]✓ Exported interactive HTML dashboard to {export_html}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to export HTML dashboard: {e}[/red]")


@cli.command("serve")
@click.argument("target_input", required=False, default=".")
@click.option("-p", "--port", type=int, default=8848, help="Port to serve dashboard on")
@click.option("-c", "--config", "config_file", type=click.Path(exists=True), help="Path to optiforge.yaml")
def serve(target_input: str, port: int, config_file: Optional[str]):
    """Launch the interactive web dashboard for a target."""
    config = OptiConfig.load(config_path=config_file)
    from optiforge.services.input_detector import InputDetector
    detected = InputDetector.detect(target_input)
    target = detected.target
    print_banner(target, dry_run=True)

    with console.status(f"[cyan]Analyzing '{target.identifier}' to populate dashboard...[/cyan]", spinner="dots"):
        findings, telemetry = registry.analyze_target(target, config)

    from optiforge.reporting.dashboard_server import start_dashboard_server
    start_dashboard_server(target, findings, telemetry, port=port)


@cli.command("fix")
@click.argument("target_input", required=False, default=".")
@click.option("-c", "--config", "config_file", type=click.Path(exists=True), help="Path to optiforge.yaml")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Explicitly apply fixes (Default is DRY-RUN)")
@click.option("--yes", "-y", is_flag=True, default=False, help="Bypass interactive confirmation prompt")
def fix(target_input: str, config_file: Optional[str], apply_changes: bool, yes: bool):
    """Safely optimize and fix detected inefficiencies in the target."""
    config = OptiConfig.load(config_path=config_file)
    from optiforge.services.input_detector import InputDetector
    detected = InputDetector.detect(target_input)
    target = detected.target
    dry_run = not apply_changes

    print_banner(target, dry_run=dry_run)

    with console.status(f"[cyan]Analyzing target '{target.identifier}' to compute fix proposals...[/cyan]", spinner="dots"):
        findings, _ = registry.analyze_target(target, config)
        proposals = registry.collect_fix_proposals(findings, target, config)

    if not proposals:
        console.print("[yellow]No automated fix proposals available for the discovered findings.[/yellow]")
        return

    print_fix_proposals(proposals, dry_run=dry_run)

    if dry_run:
        console.print("[bold cyan]To apply these optimizations safely with automatic snapshot backup, run:[/bold cyan]")
        console.print(f"  [bold green]optiforge fix \"{target_input}\" --apply[/bold green]\n")
        return

    if not yes:
        if not click.confirm("Are you sure you want to apply these optimizations? (A full rollback snapshot will be created)"):
            console.print("[yellow]Operation aborted by user.[/yellow]")
            return

    # Safety engine execution (Phase 4 integration)
    try:
        from optiforge.core.safety import SafetyEngine
        safety = SafetyEngine(config=config)
        results = safety.apply_proposals(proposals, target)
        print_fix_results(results)
    except Exception as e:
        console.print(f"[bold red]Error applying fixes: {e}[/bold red]")


@cli.command("rollback")
@click.option("--id", "backup_id", default=None, help="Specific backup ID to rollback (defaults to latest)")
@click.option("-c", "--config", "config_file", type=click.Path(exists=True), help="Path to optiforge.yaml")
def rollback(backup_id: Optional[str], config_file: Optional[str]):
    """Roll back applied fixes to an earlier snapshot."""
    config = OptiConfig.load(config_path=config_file)
    try:
        from optiforge.core.safety import SafetyEngine
        safety = SafetyEngine(config=config)
        res = safety.rollback(backup_id)
        if res.get("success"):
            console.print(f"[bold green]✓ Successfully rolled back {res.get('restored_count', 0)} files from backup '{res.get('backup_id')}'.[/bold green]")
        else:
            console.print(f"[bold red]Rollback failed: {res.get('error', 'Unknown error')}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Rollback failed: {e}[/bold red]")


@cli.command("plugins")
def list_plugins():
    """List all registered OptiForge plugins and supported target types."""
    plugins = registry.list_plugins()
    console.print(f"\n[bold cyan]Registered OptiForge Plugins ({len(plugins)}):[/bold cyan]\n")
    for p in plugins:
        kinds = ", ".join(k.value for k in p.target_kinds) if p.target_kinds else "universal"
        console.print(f"  • [bold green]{p.name}[/bold green] [dim]({kinds})[/dim]")
        console.print(f"    {p.description}\n")


@cli.command("report")
@click.argument("report_file", required=False, default="report.md")
def report(report_file: str):
    """View a generated Markdown or JSON report."""
    rf_path = Path(report_file)
    if not rf_path.exists():
        console.print(f"[yellow]Report file '{report_file}' not found. Run 'optiforge analyze --export-md report.md' first.[/yellow]")
        return

    if rf_path.suffix.lower() == ".json":
        import json
        data = json.loads(rf_path.read_text(encoding="utf-8"))
        findings_data = data.get("findings", [])
        from optiforge.core.finding import Category, Confidence, Effort, Finding, Impact
        findings = [
            Finding(
                id=d["id"],
                category=Category(d["category"]),
                title=d["title"],
                description=d["description"],
                impact=Impact(d["impact"]),
                effort=Effort(d["effort"]),
                confidence=Confidence(d["confidence"]),
                target_entity=d.get("target_entity", ""),
                metrics=d.get("metrics", {}),
                exact_fix=d.get("exact_fix"),
            )
            for d in findings_data
        ]
        print_findings_summary(findings)
        print_recommendations_matrix(findings)
    else:
        from rich.markdown import Markdown
        content = rf_path.read_text(encoding="utf-8")
        console.print(Markdown(content))


@cli.command("app")
@click.option("-p", "--port", type=int, default=None, help="Custom local port")
@click.option("--browser", is_flag=True, default=False, help="Launch in default browser instead of native window")
def run_desktop_app(port: Optional[int], browser: bool):
    """Launch the friendly OptiForge Desktop App for beginners and non-technical users."""
    from optiforge.app.main import launch_app
    launch_app(port=port, no_window=browser)


def main():
    cli()


if __name__ == "__main__":
    main()
