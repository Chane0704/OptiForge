"""Verifies analysis and feature flow on sample_bloated_project and the user's real folder: Multi-Agent Code Review."""

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from optiforge.services.input_detector import InputDetector
from optiforge.services.analysis_service import AnalysisService
from optiforge.services.prompt_service import PromptService

def run_checks():
    detector = InputDetector()
    service = AnalysisService()

    targets = [
        ("sample_bloated_project", str(ROOT / "sample_bloated_project")),
        ("Multi-Agent Code Review", "c:\\Users\\anish\\Downloads\\My Projects\\Multi-Agent Code Review"),
    ]

    print("\n" + "=" * 105)
    print(f"{'Target Name':<28} | {'Path':<50} | {'Files':<6} | {'Score':<6} | {'Savings':<10}")
    print("-" * 105)

    for name, path in targets:
        detected = detector.detect(path)
        result = service.analyze(detected)
        d = result.to_dict()

        print(f"{d['target_name']:<28} | {d['target_path']:<50} | {d['item_count']:<6} | {d['health_score']:<6.1f} | {d['total_savings_mb']:<10.2f} MB")

        # Test prompt generation
        prompt_res = PromptService.generate_full_report_prompt(result, mode="fix_safe")
        assert len(prompt_res.prompt_text) > 50, f"Prompt generation failed for {name}"

        # Test fix proposals
        proposals = service.get_fix_proposals(detected.target, result.all_findings)
        print(f"  -> Generated {len(proposals)} fix proposals, {prompt_res.secrets_redacted_count} secrets redacted.")

    print("=" * 105 + "\n")
    print("✓ Successfully verified both projects including user's 'Multi-Agent Code Review'!")

if __name__ == "__main__":
    run_checks()
