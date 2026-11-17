"""Tests for WebsiteAnalyzerPlugin."""

from pathlib import Path
import pytest
from optiforge.config import OptiConfig
from optiforge.core.finding import Category
from optiforge.core.target import Target, TargetKind
from optiforge.plugins.website_analyzer import HTMLResourceAuditor, WebsiteAnalyzerPlugin


def test_html_resource_auditor():
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script src="app.js"></script>
        <script src="deferred.js" defer></script>
        <link rel="stylesheet" href="style.css">
    </head>
    <body>
        <img src="photo.jpg">
        <img src="logo.png" width="200" height="100">
    </body>
    </html>
    """
    auditor = HTMLResourceAuditor()
    auditor.feed(sample_html)

    # Check render blocking script
    assert len(auditor.render_blocking_scripts) == 1
    assert auditor.render_blocking_scripts[0]["src"] == "app.js"

    # Check unsized image
    assert len(auditor.unsized_images) == 1
    assert auditor.unsized_images[0] == "photo.jpg"


def test_website_analyzer_local_html():
    plugin = WebsiteAnalyzerPlugin()
    target = Target(
        kind=TargetKind.CODEBASE,
        identifier="sample_bloated_project",
        path=Path("sample_bloated_project"),
    )
    config = OptiConfig()

    findings = plugin.analyze(target, config)
    categories = [f.category for f in findings]

    # Should detect render blocking scripts and CLS unsized images
    assert Category.RENDER_BLOCKING in categories
    assert Category.RUNTIME_SMOOTHNESS in categories
