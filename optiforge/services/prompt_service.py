"""AI Agent Prompt Generation Service with Automatic Secret Redaction.

Generates structured, copy-paste prompts optimized for Antigravity, Claude Code,
Cursor, and ChatGPT, while ensuring no credentials or secrets leave the machine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from optiforge.core.finding import Category, Confidence, Finding
from optiforge.services.analysis_service import FriendlyAnalysisResult, FriendlyFinding


@dataclass
class PromptGenerationResult:
    prompt_text: str
    mode: str
    detail_level: str
    secrets_redacted_count: int
    redaction_warning: Optional[str] = None
    target_name: str = ""


class SecretRedactor:
    """Detects and redacts secrets, credentials, tokens, and passwords from text and code."""

    PATTERNS: List[Tuple[str, re.Pattern]] = [
        ("OpenAI / Anthropic Key", re.compile(r"\b(sk-[a-zA-Z0-9_\-]{20,})\b")),
        ("Google API Key", re.compile(r"\b(AIza[0-9A-Za-z-_]{30,45})\b")),
        ("GitHub Personal Token", re.compile(r"\b(gh[pous]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{35,})\b")),
        ("AWS Access Key", re.compile(r"\b(AKIA[0-9A-Z]{16})\b")),
        ("Private Key Block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
        ("Database URI Password", re.compile(r"(?:postgres|postgresql|mysql|mongodb(?:\+srv)?):\/\/[^:\s]+:([^@\s]+)@")),
        ("Bearer Token", re.compile(r"(?:Bearer\s+)([a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE)),
        ("Generic Password / Secret Assignment", re.compile(r"""(?i)(?:password|secret|api_key|_key|key|token|auth_token|passwd)\s*[:=]\s*['"]([^'"]{6,})['"]""")),
    ]

    @classmethod
    def redact(cls, text: str) -> Tuple[str, int, List[str]]:
        """Redacts all detected secrets and returns (clean_text, count, secret_types)."""
        redacted_text = text
        count = 0
        detected_types: List[str] = []

        for name, pattern in cls.PATTERNS:
            def replace_match(match):
                nonlocal count
                count += 1
                if name not in detected_types:
                    detected_types.append(name)
                # If group 1 exists, replace group 1; otherwise entire match
                if match.groups():
                    matched_str = match.group(0)
                    target_sub = match.group(1)
                    return matched_str.replace(target_sub, "[REDACTED_SECRET]")
                return "[REDACTED_SECRET]"

            redacted_text = pattern.sub(replace_match, redacted_text)

        return redacted_text, count, detected_types


class PromptService:
    """Formats performance diagnostics into actionable prompts for coding agents."""

    @classmethod
    def generate_prompt_for_single_finding(
        cls,
        finding: FriendlyFinding,
        target_name: str,
        mode: str = "fix_safe",
        detail_level: str = "detailed",
    ) -> PromptGenerationResult:
        """Generates a prompt focused on fixing a specific finding."""
        raw = finding.raw_finding
        lines = [
            f"# Performance Optimization Request: {finding.friendly_title}",
            f"",
            f"You are a performance engineer optimizing the project: `{target_name}`.",
            f"",
            f"## Issue to Address",
            f"- **Title:** {finding.friendly_title}",
            f"- **Category:** {raw.category.value}",
            f"- **Target Entity:** `{raw.target_entity or raw.target_path}`",
            f"- **Why it matters:** {finding.why_it_matters}",
            f"- **Estimated Gain:** {finding.estimated_gain}",
            f"",
        ]

        if mode == "explain":
            lines.extend([
                f"## Instructions",
                f"1. Explain step-by-step why this inefficiency happens in `{raw.target_entity}`.",
                f"2. Show the before-and-after code/config diff.",
                f"3. Explain the performance benefit in simple terms.",
            ])
        else:
            lines.extend([
                f"## Required Action",
                f"{finding.what_to_do}",
                f"",
            ])
            if raw.exact_fix:
                lines.extend([
                    f"## Recommended Fix",
                    f"```text",
                    f"{raw.exact_fix}",
                    f"```",
                    f"",
                ])

            lines.extend(cls._get_safety_rules_markdown())

        full_text = "\n".join(lines)
        clean_text, count, types = SecretRedactor.redact(full_text)

        warning = None
        if count > 0:
            warning = f"🛡️ {count} secret(s) ({', '.join(types)}) were automatically redacted from this prompt for your safety."

        return PromptGenerationResult(
            prompt_text=clean_text,
            mode=mode,
            detail_level=detail_level,
            secrets_redacted_count=count,
            redaction_warning=warning,
            target_name=target_name,
        )

    @classmethod
    def generate_full_report_prompt(
        cls,
        analysis_result: FriendlyAnalysisResult,
        mode: str = "fix_safe",  # 'fix_safe' | 'fix_all' | 'explain'
        detail_level: str = "detailed",  # 'detailed' | 'short'
    ) -> PromptGenerationResult:
        """Generates a comprehensive multi-issue prompt for an AI coding agent."""
        target_name = analysis_result.detected_input.friendly_label

        # Filter findings based on selected mode
        if mode == "fix_safe":
            items = [f for f in (analysis_result.quick_wins + analysis_result.worth_doing) if f.safety_badge == "Safe"]
            scope_desc = "Fix only the safe, zero-risk optimizations"
        elif mode == "fix_all":
            items = analysis_result.quick_wins + analysis_result.worth_doing + analysis_result.optional
            scope_desc = "Address all detected performance inefficiencies"
        else:  # explain
            items = analysis_result.quick_wins + analysis_result.worth_doing
            scope_desc = "Explain the detected inefficiencies step-by-step"

        lines = [
            f"# Performance Optimization Task: {target_name}",
            f"",
            f"You are a performance engineer working in `{target_name}`.",
            f"OptiForge analyzed the project and calculated a Health Score of **{analysis_result.health_score}/100** ({analysis_result.health_label}).",
            f"Estimated potential size reduction: **{analysis_result.total_savings_mb:.2f} MB**.",
            f"",
            f"## Goal: {scope_desc}",
            f"",
        ]

        if mode == "explain":
            lines.extend([
                f"Please review the issues listed below and explain for each:",
                f"1. Why the issue impacts performance or speed.",
                f"2. What changes are needed to resolve it safely.",
                f"3. How to verify the fix works afterwards.",
                f"",
            ])
        else:
            lines.extend([
                f"Please optimize the codebase by applying the fixes described below.",
                f"",
            ])

        lines.append(f"## Issues to Resolve ({len(items)} Items)")
        lines.append("")

        for idx, item in enumerate(items, 1):
            lines.append(f"### {idx}. {item.friendly_title}")
            lines.append(f"- **Target:** `{item.target_entity}`")
            lines.append(f"- **Safety Level:** {item.safety_badge} | **Gain:** {item.estimated_gain}")
            lines.append(f"- **Why it matters:** {item.why_it_matters}")
            lines.append(f"- **What to do:** {item.what_to_do}")

            if detail_level == "detailed" and item.raw_finding.exact_fix:
                lines.append(f"- **Suggested Fix:**")
                lines.append(f"  ```text")
                lines.append(f"  {item.raw_finding.exact_fix}")
                lines.append(f"  ```")
            lines.append("")

        lines.extend(cls._get_safety_rules_markdown())

        full_text = "\n".join(lines)
        clean_text, count, types = SecretRedactor.redact(full_text)

        warning = None
        if count > 0:
            warning = f"🛡️ {count} secret(s) ({', '.join(types)}) were automatically redacted from this prompt for your safety."

        return PromptGenerationResult(
            prompt_text=clean_text,
            mode=mode,
            detail_level=detail_level,
            secrets_redacted_count=count,
            redaction_warning=warning,
            target_name=target_name,
        )

    @staticmethod
    def _get_safety_rules_markdown() -> List[str]:
        return [
            f"## Mandatory Safety Rules",
            f"1. **Safety First**: Make a git commit or copy files to a backup directory before modifying anything.",
            f"2. **Never Delete Files**: If removing duplicate files or dead code, move them to a backup or quarantine directory instead of deleting.",
            f"3. **Small Changes**: Make atomic, focused edits one file at a time.",
            f"4. **Explain Every Change**: Briefly explain the changes made in each file.",
            f"5. **Verify Afterwards**: Check that the project builds, runs, and passes existing tests after applying your fixes.",
        ]
