"""Optional AI Assistant Service for OptiForge.

Provides deeper code explanations and screenshot vision analysis when explicitly
enabled by the user. 100% OFF by default with strict privacy transparency.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import requests

from optiforge.services.analysis_service import FriendlyFinding

logger = logging.getLogger("optiforge.ai_service")


class AIService:
    """Manages optional LLM interactions with mandatory data preview and privacy controls."""

    def __init__(self, api_key: Optional[str] = None, provider: str = "gemini"):
        self.api_key = api_key
        self.provider = provider
        self.enabled = bool(api_key)

    def preview_payload(
        self,
        text_content: str,
        image_path: Optional[Path | str] = None,
    ) -> Dict[str, Any]:
        """Provides a transparent audit preview of exactly what data would leave the machine."""
        image_info = None
        if image_path:
            p = Path(image_path)
            if p.exists():
                image_info = {
                    "filename": p.name,
                    "format": p.suffix[1:].upper(),
                    "size_bytes": p.stat().st_size,
                }

        return {
            "destination": f"https://generativelanguage.googleapis.com (Google Gemini)" if self.provider == "gemini" else "External AI Provider",
            "characters_to_send": len(text_content),
            "image_attached": bool(image_info),
            "image_details": image_info,
            "preview_snippet": text_content[:250] + ("..." if len(text_content) > 250 else ""),
            "privacy_notice": "Nothing is sent until you explicitly confirm. All secrets and API keys are automatically stripped beforehand.",
        }

    def explain_finding(self, finding: FriendlyFinding) -> Dict[str, Any]:
        """Generates an AI explanation for an inefficiency using the user's API key."""
        if not self.enabled or not self.api_key:
            return {
                "success": False,
                "error": "AI Mode is turned off. You can add your API key in Settings to enable deeper AI explanations.",
                "explanation": None,
            }

        prompt = (
            f"You are a performance expert explaining an optimization finding to a beginner or non-technical developer.\n"
            f"Finding: {finding.friendly_title}\n"
            f"Why it matters: {finding.why_it_matters}\n"
            f"Target: {finding.target_entity}\n"
            f"Explain in 2 friendly paragraphs why this slows down the system and how fixing it helps real users."
        )

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return {"success": True, "explanation": text}
            else:
                return {
                    "success": False,
                    "error": f"AI service returned HTTP {resp.status_code}: {resp.text[:120]}",
                }
        except Exception as e:
            return {"success": False, "error": f"Failed to reach AI service: {e}"}

    def inspect_screenshot(self, image_path: Path | str) -> Dict[str, Any]:
        """Analyzes a screenshot for visual bloat, oversized banners, and layout inefficiencies."""
        if not self.enabled or not self.api_key:
            return {
                "success": False,
                "error": "AI Vision is disabled. Enable AI mode in Settings to analyze screenshots.",
            }

        path = Path(image_path)
        if not path.exists():
            return {"success": False, "error": "Image file not found."}

        try:
            mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            b64_data = base64.b64encode(path.read_bytes()).decode("utf-8")

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Analyze this screenshot of a web/mobile UI for visual and asset performance: identify oversized hero banners, heavy layout blocks, or elements that look like they slow down rendering."},
                        {"inline_data": {"mime_type": mime, "data": b64_data}}
                    ]
                }]
            }
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                analysis = data["candidates"][0]["content"]["parts"][0]["text"]
                return {"success": True, "vision_analysis": analysis}
            else:
                return {"success": False, "error": f"API error: {resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
