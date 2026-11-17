"""Tests for CompressorPlugin and CodeMinifier."""

from pathlib import Path
import pytest
from PIL import Image
from optiforge.config import OptiConfig
from optiforge.core.finding import Category
from optiforge.core.target import Target, TargetKind
from optiforge.plugins.compressor import CodeMinifier, CompressorPlugin


def test_code_minifier_css():
    css = """
    /* Header styles */
    header {
        color: #ffffff ;
        margin: 10px ;
    }
    """
    minified = CodeMinifier.minify_css(css)
    assert "/*" not in minified
    assert minified == "header{color:#ffffff;margin:10px}"


def test_code_minifier_html():
    html = """
    <!-- Comment to be removed -->
    <div>
        <p> Hello World </p>
    </div>
    """
    minified = CodeMinifier.minify_html(html)
    assert "<!--" not in minified
    assert "><" in minified


def test_code_minifier_js():
    js = """
    // Line comment
    function hello() {
        /* Block comment */
        return 42;
    }
    """
    minified = CodeMinifier.minify_js(js)
    assert "// Line comment" not in minified
    assert "/* Block comment */" not in minified
    assert "return 42;" in minified


def test_compressor_plugin_on_bloated_project():
    plugin = CompressorPlugin()
    target = Target(
        kind=TargetKind.CODEBASE,
        identifier="sample_bloated_project",
        path=Path("sample_bloated_project"),
    )
    config = OptiConfig()

    findings = plugin.analyze(target, config)
    assert len(findings) > 0

    # Ensure heavy BMP is flagged with large savings
    bmp_findings = [f for f in findings if "heavy_photo.bmp" in f.title]
    assert len(bmp_findings) == 1
    f = bmp_findings[0]
    assert f.metrics["bytes_saved"] > 100 * 1024  # saves > 100KB!

    # Test fix proposals
    proposals = plugin.propose_fixes(findings, target, config)
    assert len(proposals) > 0
    img_proposals = [p for p in proposals if p.action_type == "convert_image_webp"]
    assert len(img_proposals) >= 1
