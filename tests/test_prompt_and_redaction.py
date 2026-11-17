"""Tests for PromptService and SecretRedactor."""

import pytest
from optiforge.core.finding import Category, Confidence, Effort, Finding, Impact
from optiforge.services.analysis_service import FriendlyFinding
from optiforge.services.input_detector import InputDetector
from optiforge.services.analysis_service import AnalysisService
from optiforge.services.prompt_service import PromptService, SecretRedactor


def test_secret_redactor():
    raw_text = """
    Here are my project credentials:
    OPENAI_KEY = "sk-abcdef1234567890abcdef1234567890"
    GEMINI_KEY = "AIzaSyD1234567890abcdef1234567890123"
    GITHUB_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuv"
    AWS_KEY = "AKIA1234567890ABCDEF"
    DB_URL = "postgres://admin:SuperSecretPass123@localhost:5432/mydb"
    """

    cleaned, count, types = SecretRedactor.redact(raw_text)
    assert count >= 4
    assert "sk-" not in cleaned
    assert "AIzaSy" not in cleaned
    assert "ghp_" not in cleaned
    assert "SuperSecretPass123" not in cleaned
    assert "[REDACTED_SECRET]" in cleaned


def test_prompt_service_modes():
    detected = InputDetector.detect("sample_bloated_project")
    result = AnalysisService.analyze(detected)

    # 1. Mode: fix_safe
    prompt_safe = PromptService.generate_full_report_prompt(result, mode="fix_safe", detail_level="detailed")
    assert prompt_safe.secrets_redacted_count >= 0
    assert "Mandatory Safety Rules" in prompt_safe.prompt_text
    assert "Never Delete Files" in prompt_safe.prompt_text

    # 2. Mode: fix_all
    prompt_all = PromptService.generate_full_report_prompt(result, mode="fix_all", detail_level="short")
    assert "Performance Optimization Task" in prompt_all.prompt_text

    # 3. Mode: explain
    prompt_explain = PromptService.generate_full_report_prompt(result, mode="explain", detail_level="detailed")
    assert "Explain each fix" in prompt_explain.prompt_text or "explain" in prompt_explain.prompt_text.lower()


def test_prompt_service_single_finding():
    finding = FriendlyFinding(
        id="OPT-TEST-001",
        friendly_title="Uncompressed Hero Banner",
        why_it_matters="Slows down page display for users",
        what_to_do="Convert to modern WebP format",
        estimated_gain="Saves 1.8 MB",
        safety_badge="Safe",
        group="quick_wins",
        target_entity="images/hero_banner.png",
        raw_finding=Finding(
            id="OPT-TEST-001",
            category=Category.ASSET_BLOAT,
            title="Uncompressed Image",
            description="PNG is 1.8 MB",
            impact=Impact.HIGH,
            effort=Effort.TRIVIAL,
            confidence=Confidence.SAFE,
            exact_fix="Convert to WebP",
        )
    )

    res = PromptService.generate_prompt_for_single_finding(finding, target_name="My Web App")
    assert "Uncompressed Hero Banner" in res.prompt_text
    assert "Mandatory Safety Rules" in res.prompt_text
