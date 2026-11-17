"""Embedded HTTP Server and HTML Dashboard Generator for OptiForge."""

from __future__ import annotations

import datetime
import http.server
import json
import logging
import socketserver
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from optiforge.core.finding import Finding
from optiforge.core.recommendation import RecommendationsEngine
from optiforge.core.target import Target

logger = logging.getLogger("optiforge.dashboard")


def build_report_payload(target: Target, findings: List[Finding], telemetry: Dict[str, Any]) -> Dict[str, Any]:
    ranked = RecommendationsEngine.rank_findings(findings)
    summary = RecommendationsEngine.generate_summary(ranked)
    total_savings_bytes = sum(f.metrics.get("bytes_saved", 0) for f in findings)

    return {
        "target": target.identifier,
        "target_kind": target.kind.value,
        "scan_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_findings": len(findings),
        "total_savings_mb": round(total_savings_bytes / (1024 * 1024), 2),
        "summary": summary,
        "findings": [f.to_dict() for f in findings],
        "telemetry": telemetry,
    }


def export_standalone_dashboard(
    target: Target,
    findings: List[Finding],
    telemetry: Dict[str, Any],
    output_path: str | Path,
) -> Path:
    """Exports a single-file, self-contained HTML dashboard with embedded data."""
    template_path = Path(__file__).parent.parent / "dashboard" / "template.html"
    template_content = template_path.read_text(encoding="utf-8")

    payload = build_report_payload(target, findings, telemetry)
    json_str = json.dumps(payload, indent=2)

    # Inject data into template
    embedded_script = f"<script>window.__OPTIFORGE_DATA__ = {json_str};</script>"
    rendered = template_content.replace("<script>", f"{embedded_script}\n    <script>", 1)

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(rendered, encoding="utf-8")
    return out_file


class DashboardHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Handles requests for the OptiForge dashboard and JSON API."""

    def __init__(self, *args, payload: Optional[Dict[str, Any]] = None, **kwargs):
        self.payload = payload or {}
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(self.payload).encode("utf-8"))
        elif self.path in ("/", "/index.html"):
            template_path = Path(__file__).parent.parent / "dashboard" / "template.html"
            content = template_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()


def start_dashboard_server(
    target: Target,
    findings: List[Finding],
    telemetry: Dict[str, Any],
    port: int = 8848,
):
    """Starts a local HTTP server serving the dashboard."""
    payload = build_report_payload(target, findings, telemetry)

    def handler(*args, **kwargs):
        return DashboardHTTPRequestHandler(*args, payload=payload, **kwargs)

    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"\n⚡ OptiForge Dashboard live at: http://localhost:{port}")
        print("Press Ctrl+C to stop server.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down dashboard server.")
