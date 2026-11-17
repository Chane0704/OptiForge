"""Website and Web Performance Analyzer Plugin for OptiForge."""

from __future__ import annotations

import logging
import re
import time
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests

from optiforge.config import OptiConfig
from optiforge.core.finding import Category, Confidence, Effort, Finding, Impact
from optiforge.core.plugin_base import AnalyzerPlugin
from optiforge.core.target import Target, TargetKind

logger = logging.getLogger("optiforge.website_analyzer")


class HTMLResourceAuditor(HTMLParser):
    """Parses HTML DOM to detect render-blocking scripts, un-sized images, and asset links."""

    def __init__(self):
        super().__init__()
        self.in_head = False
        self.render_blocking_scripts: List[Dict[str, str]] = []
        self.stylesheets: List[str] = []
        self.unsized_images: List[str] = []
        self.all_images: List[Dict[str, Any]] = []
        self.scripts: List[Dict[str, str]] = []
        self.inline_style_bytes: int = 0
        self.inline_script_bytes: int = 0
        self._current_tag: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        self._current_tag = tag.lower()

        if self._current_tag == "head":
            self.in_head = True
        elif self._current_tag == "body":
            self.in_head = False

        if self._current_tag == "script":
            src = attr_dict.get("src", "")
            is_async = "async" in attr_dict
            is_defer = "defer" in attr_dict
            is_module = attr_dict.get("type", "") == "module"

            script_info = {"src": src, "async": is_async, "defer": is_defer, "module": is_module, "in_head": self.in_head}
            self.scripts.append(script_info)

            if self.in_head and src and not (is_async or is_defer or is_module):
                self.render_blocking_scripts.append(script_info)

        elif self._current_tag == "link":
            rel = attr_dict.get("rel", "").lower()
            href = attr_dict.get("href", "")
            media = attr_dict.get("media", "").lower()
            if "stylesheet" in rel and href:
                if not media or media == "all" or media == "screen":
                    self.stylesheets.append(href)

        elif self._current_tag == "img":
            src = attr_dict.get("src", "")
            width = attr_dict.get("width")
            height = attr_dict.get("height")
            has_dimensions = bool(width and height)
            self.all_images.append({"src": src, "width": width, "height": height})
            if not has_dimensions:
                self.unsized_images.append(src)

    def handle_endtag(self, tag: str):
        if tag.lower() == "head":
            self.in_head = False
        self._current_tag = None

    def handle_data(self, data: str):
        if self._current_tag == "style":
            self.inline_style_bytes += len(data.encode("utf-8"))
        elif self._current_tag == "script":
            self.inline_script_bytes += len(data.encode("utf-8"))


class WebsiteAnalyzerPlugin(AnalyzerPlugin):
    """Audits website TTFB, Core Web Vitals indicators, compression, caching, and render-blocking assets."""

    name = "website_analyzer"
    description = "Analyzes website response times, Core Web Vitals heuristics, render-blocking scripts, and caching headers."
    target_kinds = [TargetKind.WEBSITE, TargetKind.CODEBASE]

    def can_handle(self, target: Target) -> bool:
        if target.kind == TargetKind.WEBSITE:
            return True
        if target.kind == TargetKind.CODEBASE and target.path:
            # Check if directory contains index.html
            if (target.path / "index.html").exists() or target.path.suffix.lower() in (".html", ".htm"):
                return True
        return False

    def analyze(self, target: Target, config: OptiConfig) -> List[Finding]:
        findings: List[Finding] = []

        if target.kind == TargetKind.WEBSITE and target.url:
            findings.extend(self._audit_remote_url(target, config))
        elif target.path:
            html_file = target.path if target.path.is_file() else (target.path / "index.html")
            if html_file.exists():
                findings.extend(self._audit_local_html(html_file, config))

        return findings

    def _audit_remote_url(self, target: Target, config: OptiConfig) -> List[Finding]:
        findings: List[Finding] = []
        url = target.url
        assert url is not None

        headers = {
            "User-Agent": "OptiForge-Performance-Bot/1.0",
            "Accept-Encoding": "gzip, deflate, br",
        }

        try:
            start_time = time.perf_counter()
            resp = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
            total_duration_ms = (time.perf_counter() - start_time) * 1000.0
            ttfb_ms = resp.elapsed.total_seconds() * 1000.0

            content_size = len(resp.content)
            encoding = resp.headers.get("Content-Encoding", "").lower()
            cache_control = resp.headers.get("Cache-Control", "")
            etag = resp.headers.get("ETag", "")

            target.metadata.update({
                "http_status": resp.status_code,
                "ttfb_ms": round(ttfb_ms, 1),
                "total_duration_ms": round(total_duration_ms, 1),
                "content_bytes": content_size,
                "content_encoding": encoding or "none",
                "cache_control": cache_control,
            })

            # 1. TTFB Audit
            if ttfb_ms > config.thresholds.slow_ttfb_ms:
                findings.append(Finding(
                    id="OPT-WEB-TTFB-001",
                    category=Category.SLOW_TTFB,
                    title=f"Slow Time to First Byte (TTFB: {ttfb_ms:.0f}ms)",
                    description=(
                        f"The server took {ttfb_ms:.0f}ms to respond, exceeding the recommended limit of "
                        f"{config.thresholds.slow_ttfb_ms:.0f}ms. High TTFB delays DOM parsing and degrades Core Web Vitals (LCP)."
                    ),
                    impact=Impact.HIGH,
                    effort=Effort.MODERATE,
                    confidence=Confidence.SAFE,
                    target_entity=url,
                    metrics={"ttfb_ms": ttfb_ms, "threshold": config.thresholds.slow_ttfb_ms},
                    exact_fix="Implement edge caching / CDN (Cloudflare, Cloud Front), database query caching, or server-side response caching.",
                    plugin_name=self.name,
                ))

            # 2. Compression Header Audit
            if "gzip" not in encoding and "br" not in encoding and content_size > 1024:
                potential_savings_kb = (content_size * 0.7) / 1024
                findings.append(Finding(
                    id="OPT-WEB-COMP-001",
                    category=Category.MISSING_COMPRESSION,
                    title="Missing Gzip/Brotli HTTP Compression",
                    description=(
                        f"Response payload ({content_size / 1024:.1f} KB) was served uncompressed. "
                        f"Enabling Brotli or Gzip typically reduces HTML/text payload sizes by ~65-75% (~{potential_savings_kb:.1f} KB savings)."
                    ),
                    impact=Impact.HIGH,
                    effort=Effort.TRIVIAL,
                    confidence=Confidence.SAFE,
                    target_entity=url,
                    metrics={"uncompressed_bytes": content_size, "potential_savings_kb": potential_savings_kb},
                    exact_fix="Enable gzip or brotli compression on reverse proxy/web server (e.g. Nginx 'gzip on; gzip_types text/html text/css application/javascript;', Caddy, or Express 'compression()' middleware).",
                    plugin_name=self.name,
                ))

            # 3. Browser Caching Audit
            if not cache_control and not etag:
                findings.append(Finding(
                    id="OPT-WEB-CACHE-001",
                    category=Category.CONFIG_TUNING,
                    title="Missing Cache-Control or ETag Headers",
                    description="The server did not return Cache-Control or ETag headers. Repeat visits will unnecessarily re-download unmodified assets.",
                    impact=Impact.MEDIUM,
                    effort=Effort.TRIVIAL,
                    confidence=Confidence.SAFE,
                    target_entity=url,
                    exact_fix="Set 'Cache-Control: public, max-age=31536000, immutable' for hashed static assets, and 'no-cache' with ETag for dynamic HTML.",
                    plugin_name=self.name,
                ))

            # 4. Parse DOM for Render Blocking & Web Vitals
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" in content_type:
                html_text = resp.text
                findings.extend(self._audit_html_content(html_text, url))

        except requests.RequestException as e:
            findings.append(Finding(
                id="OPT-WEB-ERR-001",
                category=Category.SLOW_TTFB,
                title="Website Request Failed",
                description=f"Could not reach '{url}': {e}",
                impact=Impact.HIGH,
                effort=Effort.TRIVIAL,
                confidence=Confidence.SAFE,
                target_entity=url,
                plugin_name=self.name,
            ))

        return findings

    def _audit_local_html(self, html_file: Path, config: OptiConfig) -> List[Finding]:
        """Audits a local HTML file directly without requiring an active HTTP server."""
        try:
            content = html_file.read_text(encoding="utf-8", errors="ignore")
            return self._audit_html_content(content, str(html_file))
        except Exception as e:
            logger.error(f"Error reading local HTML {html_file}: {e}")
            return []

    def _audit_html_content(self, html_text: str, source_label: str) -> List[Finding]:
        findings: List[Finding] = []
        auditor = HTMLResourceAuditor()
        try:
            auditor.feed(html_text)
        except Exception:
            pass

        # 1. Render-blocking scripts
        if auditor.render_blocking_scripts:
            scripts_list = [s["src"] for s in auditor.render_blocking_scripts]
            findings.append(Finding(
                id="OPT-WEB-BLOCK-001",
                category=Category.RENDER_BLOCKING,
                title=f"Detected {len(auditor.render_blocking_scripts)} Render-Blocking Script(s) in <head>",
                description=(
                    f"Synchronous scripts in <head> block the HTML parser and delay First Contentful Paint (FCP): "
                    f"{', '.join(scripts_list[:3])}{'...' if len(scripts_list) > 3 else ''}."
                ),
                impact=Impact.HIGH,
                effort=Effort.TRIVIAL,
                confidence=Confidence.SAFE,
                target_entity=source_label,
                metrics={"blocking_scripts_count": len(auditor.render_blocking_scripts), "scripts": scripts_list},
                exact_fix="Add 'defer' or 'async' attribute to external <script> tags, or move non-critical scripts to the bottom of <body>.",
                plugin_name=self.name,
            ))

        # 2. Cumulative Layout Shift (CLS) Risk: Missing image dimensions
        if auditor.unsized_images:
            findings.append(Finding(
                id="OPT-WEB-CLS-001",
                category=Category.RUNTIME_SMOOTHNESS,
                title=f"CLS Vulnerability: {len(auditor.unsized_images)} Image(s) Missing Explicit Width/Height",
                description=(
                    f"Images without 'width' and 'height' attributes cause sudden layout shifts as they load, worsening Cumulative Layout Shift (CLS): "
                    f"{', '.join(auditor.unsized_images[:3])}."
                ),
                impact=Impact.MEDIUM,
                effort=Effort.EASY,
                confidence=Confidence.SAFE,
                target_entity=source_label,
                metrics={"unsized_count": len(auditor.unsized_images)},
                exact_fix="Add explicit 'width' and 'height' or CSS 'aspect-ratio' attributes to all <img> tags.",
                plugin_name=self.name,
            ))

        # 3. Excessive Inline Styles/Scripts
        if auditor.inline_style_bytes > 50 * 1024:
            findings.append(Finding(
                id="OPT-WEB-INLINE-001",
                category=Category.ASSET_BLOAT,
                title=f"Excessive Inline CSS ({auditor.inline_style_bytes / 1024:.1f} KB)",
                description="Large blocks of inline <style> prevent browser CSS caching across page navigations.",
                impact=Impact.MEDIUM,
                effort=Effort.EASY,
                confidence=Confidence.SAFE,
                target_entity=source_label,
                exact_fix="Extract inline styles into an external stylesheet cached with long-lived headers.",
                plugin_name=self.name,
            ))

        return findings
