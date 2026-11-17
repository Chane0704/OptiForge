"""Compression and Size Optimizer Plugin for OptiForge."""

from __future__ import annotations

import io
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

from optiforge.config import OptiConfig
from optiforge.core.finding import Category, Confidence, Effort, Finding, FixProposal, Impact
from optiforge.core.plugin_base import OptimizerPlugin
from optiforge.core.target import Target, TargetKind

logger = logging.getLogger("optiforge.compressor")


class CodeMinifier:
    """Safe, lightweight minifier for JS, CSS, and HTML without external dependencies."""

    @staticmethod
    def minify_css(css: str) -> str:
        # Strip comments
        css = re.sub(r"/\*[\s\S]*?\*/", "", css)
        # Collapse whitespace
        css = re.sub(r"\s+", " ", css)
        # Remove space around delimiters
        css = re.sub(r"\s*([\{\}:;,])\s*", r"\1", css)
        css = re.sub(r";\}", "}", css)
        return css.strip()

    @staticmethod
    def minify_html(html: str) -> str:
        # Strip comments (preserve conditional comments)
        html = re.sub(r"<!--(?!\s*\[if)[\s\S]*?-->", "", html)
        # Collapse consecutive whitespace between tags
        html = re.sub(r">\s+<", "><", html)
        return html.strip()

    @staticmethod
    def minify_js(js: str) -> str:
        """Minifies JS by removing multiline comments and trailing whitespace safely."""
        # Remove multiline comments
        js = re.sub(r"/\*[\s\S]*?\*/", "", js)
        # Remove single line comments that are not part of URLs or strings
        lines = []
        for line in js.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("//"):
                continue
            # Trim trailing spaces
            lines.append(line.rstrip())
        # Join lines and collapse redundant empty lines
        joined = "\n".join(lines)
        joined = re.sub(r"\n{2,}", "\n", joined)
        return joined.strip()


class CompressorPlugin(OptimizerPlugin):
    """Audits and compresses images, minifies code assets, and reports byte-for-byte savings."""

    name = "compressor"
    description = "Optimizes images (converts to modern WebP, resizes) and minifies static JS/CSS/HTML assets."
    target_kinds = [TargetKind.CODEBASE]

    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}
    CODE_EXTS = {".css", ".js", ".mjs", ".html"}

    def can_handle(self, target: Target) -> bool:
        if target.kind == TargetKind.CODEBASE and target.path:
            return True
        return False

    def analyze(self, target: Target, config: OptiConfig) -> List[Finding]:
        findings: List[Finding] = []
        if not target.path or not target.path.exists():
            return findings

        # Collect files to analyze
        root_path = target.path
        if root_path.is_file():
            files = [root_path]
        else:
            files = []
            for dirpath, dirnames, filenames in os.walk(root_path):
                rel_dir = os.path.relpath(dirpath, root_path)
                if config.is_path_ignored(rel_dir):
                    dirnames[:] = []  # prune directory walk
                    continue

                for f in filenames:
                    rel_file = os.path.normpath(os.path.join(rel_dir, f))
                    if not config.is_path_ignored(rel_file):
                        files.append(Path(dirpath) / f)

        for file_path in files:
            ext = file_path.suffix.lower()
            if ext in self.IMAGE_EXTS:
                img_finding = self._analyze_image(file_path, root_path, config)
                if img_finding:
                    findings.append(img_finding)
            elif ext in self.CODE_EXTS:
                code_finding = self._analyze_code_file(file_path, root_path, config)
                if code_finding:
                    findings.append(code_finding)

        return findings

    def _analyze_image(self, file_path: Path, root_path: Path, config: OptiConfig) -> Optional[Finding]:
        """Examines an image and computes potential savings from WebP conversion or compression."""
        try:
            raw_size = file_path.stat().st_size
            if raw_size < 1024:  # Skip tiny icons < 1KB
                return None

            with Image.open(file_path) as img:
                width, height = img.size
                orig_format = img.format or file_path.suffix[1:].upper()

                # If BMP or uncompressed format, immediate flag
                is_raw_bitmap = orig_format in ("BMP", "TIFF")

                # Test compression to WebP in memory
                buffer = io.BytesIO()
                webp_quality = int(config.plugins.get(self.name, {}).get("webp_quality", 80))
                
                # Convert RGBA/RGB safely
                conv_img = img
                if img.mode not in ("RGB", "RGBA"):
                    conv_img = img.convert("RGBA" if "A" in img.mode else "RGB")

                conv_img.save(buffer, format="WEBP", quality=webp_quality, method=4)
                webp_size = buffer.tell()

                bytes_saved = raw_size - webp_size
                percent_saved = (bytes_saved / raw_size) * 100.0

                # Check if file is oversized or can save significant bytes (>20% and >10KB or is BMP)
                is_oversized = (raw_size > config.thresholds.oversized_asset_kb * 1024) or (width > 2560 or height > 2560)

                if is_raw_bitmap or (bytes_saved > 8192 and percent_saved >= 18.0) or is_oversized:
                    rel_path = file_path.relative_to(root_path) if file_path.is_relative_to(root_path) else file_path.name
                    title = f"Unoptimized Image: '{rel_path}' can save {bytes_saved / 1024:.1f} KB ({percent_saved:.0f}%)"
                    desc = (
                        f"Image '{rel_path}' is {raw_size / 1024:.1f} KB ({width}x{height} {orig_format}). "
                        f"Converting to modern WebP (quality {webp_quality}) reduces file size to {webp_size / 1024:.1f} KB "
                        f"(saving {bytes_saved / 1024:.1f} KB, -{percent_saved:.0f}%)."
                    )

                    impact = Impact.HIGH if bytes_saved > 100 * 1024 else Impact.MEDIUM
                    return Finding(
                        id=f"OPT-IMG-{abs(hash(str(rel_path))) % 10000:04d}",
                        category=Category.ASSET_BLOAT,
                        title=title,
                        description=desc,
                        impact=impact,
                        effort=Effort.TRIVIAL,
                        confidence=Confidence.SAFE,
                        target_entity=str(rel_path),
                        target_path=file_path,
                        metrics={
                            "original_bytes": raw_size,
                            "optimized_bytes": webp_size,
                            "bytes_saved": bytes_saved,
                            "percent_saved": round(percent_saved, 1),
                            "dimensions": f"{width}x{height}",
                            "format": orig_format,
                        },
                        exact_fix=f"Convert to WebP format using OptiForge auto-fix or Pillow/cwebp.",
                        plugin_name=self.name,
                    )
        except Exception as e:
            logger.debug(f"Failed to inspect image {file_path}: {e}")
            return None
        return None

    def _analyze_code_file(self, file_path: Path, root_path: Path, config: OptiConfig) -> Optional[Finding]:
        """Examines JS/CSS/HTML files and checks potential minification savings."""
        filename = file_path.name.lower()
        if ".min." in filename or "-min." in filename:
            return None

        try:
            raw_size = file_path.stat().st_size
            if raw_size < 1024:  # Skip tiny files < 1KB
                return None

            content = file_path.read_text(encoding="utf-8", errors="ignore")
            ext = file_path.suffix.lower()

            if ext == ".css":
                minified = CodeMinifier.minify_css(content)
            elif ext in (".js", ".mjs"):
                minified = CodeMinifier.minify_js(content)
            elif ext == ".html":
                minified = CodeMinifier.minify_html(content)
            else:
                return None

            min_size = len(minified.encode("utf-8"))
            bytes_saved = raw_size - min_size
            percent_saved = (bytes_saved / raw_size) * 100.0 if raw_size else 0

            if bytes_saved > 1024 and percent_saved >= 15.0:
                rel_path = file_path.relative_to(root_path) if file_path.is_relative_to(root_path) else file_path.name
                title = f"Unminified {ext[1:].upper()} File: '{rel_path}' (-{bytes_saved / 1024:.1f} KB / -{percent_saved:.0f}%)"
                desc = (
                    f"File '{rel_path}' is {raw_size / 1024:.1f} KB uncompressed with redundant whitespace, comments, or syntax overhead. "
                    f"Minification shrinks it to {min_size / 1024:.1f} KB, saving {bytes_saved / 1024:.1f} KB (-{percent_saved:.0f}%)."
                )

                return Finding(
                    id=f"OPT-MIN-{abs(hash(str(rel_path))) % 10000:04d}",
                    category=Category.ASSET_BLOAT,
                    title=title,
                    description=desc,
                    impact=Impact.MEDIUM if bytes_saved > 20 * 1024 else Impact.LOW,
                    effort=Effort.TRIVIAL,
                    confidence=Confidence.SAFE,
                    target_entity=str(rel_path),
                    target_path=file_path,
                    metrics={
                        "original_bytes": raw_size,
                        "minified_bytes": min_size,
                        "bytes_saved": bytes_saved,
                        "percent_saved": round(percent_saved, 1),
                    },
                    exact_fix=f"Minify asset during build step or use OptiForge auto-fix.",
                    plugin_name=self.name,
                )
        except Exception as e:
            logger.debug(f"Failed to inspect code file {file_path}: {e}")
            return None
        return None

    def propose_fixes(self, findings: List[Finding], target: Target, config: OptiConfig) -> List[FixProposal]:
        """Generates concrete fix proposals for image compression and asset minification."""
        proposals: List[FixProposal] = []

        for finding in findings:
            if finding.plugin_name != self.name or not finding.target_path:
                continue

            # Image Optimization Fix
            if finding.id.startswith("OPT-IMG-") and finding.target_path.exists():
                orig_path = finding.target_path
                savings = finding.metrics.get("bytes_saved", 0)
                webp_quality = int(config.plugins.get(self.name, {}).get("webp_quality", 80))

                def make_convert_action(source_img_path: Path, quality: int):
                    def convert_action():
                        dest_path = source_img_path.with_suffix(".webp")
                        with Image.open(source_img_path) as img:
                            conv = img.convert("RGBA" if "A" in img.mode else "RGB") if img.mode not in ("RGB", "RGBA") else img
                            conv.save(dest_path, format="WEBP", quality=quality, method=4)
                        return dest_path
                    return convert_action

                proposals.append(FixProposal(
                    finding_id=finding.id,
                    action_type="convert_image_webp",
                    target_path=orig_path,
                    description=f"Convert '{orig_path.name}' to optimized WebP (saves ~{savings / 1024:.1f} KB)",
                    preview_diff=f"Source: {orig_path} -> Target: {orig_path.with_suffix('.webp')}",
                    estimated_savings_bytes=savings,
                    custom_action=make_convert_action(orig_path, webp_quality),
                ))

            # Code Minification Fix
            elif finding.id.startswith("OPT-MIN-") and finding.target_path.exists():
                file_path = finding.target_path
                ext = file_path.suffix.lower()
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    if ext == ".css":
                        minified = CodeMinifier.minify_css(content)
                    elif ext in (".js", ".mjs"):
                        minified = CodeMinifier.minify_js(content)
                    elif ext == ".html":
                        minified = CodeMinifier.minify_html(content)
                    else:
                        continue

                    savings = len(content.encode("utf-8")) - len(minified.encode("utf-8"))
                    proposals.append(FixProposal(
                        finding_id=finding.id,
                        action_type="modify_file",
                        target_path=file_path,
                        description=f"Minify whitespace and comments in '{file_path.name}' (saves ~{savings / 1024:.1f} KB)",
                        preview_diff=f"Original lines: {len(content.splitlines())} -> Minified lines: {len(minified.splitlines())}",
                        estimated_savings_bytes=savings,
                        replacement_content=minified,
                    ))
                except Exception as e:
                    logger.debug(f"Could not build minification fix for {file_path}: {e}")

        return proposals
