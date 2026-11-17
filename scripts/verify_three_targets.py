"""Runs the analysis service across three distinct projects and outputs a side-by-side comparison table."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from optiforge.services.input_detector import InputDetector
from optiforge.services.analysis_service import AnalysisService

def test_three_targets():
    detector = InputDetector()
    service = AnalysisService()

    targets = [
        ("sample_bloated_project", ROOT / "sample_bloated_project"),
        ("clean_project", ROOT / "test_targets" / "clean_project"),
        ("minimal_project", ROOT / "test_targets" / "minimal_project"),
    ]

    results = []

    for name, path in targets:
        detected = detector.detect(str(path))
        result = service.analyze(detected)
        d = result.to_dict()
        results.append(d)

    print("\n" + "=" * 95)
    print(f"{'Target Name':<24} | {'Score':<8} | {'Savings (MB)':<14} | {'Speed Gain':<16} | {'Findings':<10} | {'Safe Fixes':<10}")
    print("-" * 95)

    for r in results:
        total_findings = len(r.get("quick_wins", [])) + len(r.get("worth_doing", [])) + len(r.get("optional", []))
        print(f"{r['target_name']:<24} | {r['health_score']:<8.1f} | {r['total_savings_mb']:<14} | {r['estimated_speed_gain']:<16} | {total_findings:<10} | {r['safe_fixes_count']:<10}")
    print("=" * 95 + "\n")

    # Assertions
    # 1. Scores must not all be identical
    scores = [r["health_score"] for r in results]
    assert len(set(scores)) == 3, f"Expected 3 distinct health scores, got {scores}"

    # 2. Savings must not all be identical
    savings = [r["total_savings_mb"] for r in results]
    assert len(set(savings)) >= 2, f"Expected distinct savings, got {savings}"

    # 3. Clean project should have 100 score and 0 findings
    clean_res = [r for r in results if r["target_name"] == "clean_project"][0]
    clean_findings = len(clean_res.get("quick_wins", [])) + len(clean_res.get("worth_doing", [])) + len(clean_res.get("optional", []))
    assert clean_res["health_score"] == 100.0, f"Clean project score should be 100, got {clean_res['health_score']}"
    assert clean_findings == 0, f"Clean project should have 0 findings, got {clean_findings}"
    assert clean_res["total_savings_mb"] == 0.0, f"Clean project savings should be 0.0 MB, got {clean_res['total_savings_mb']}"

    # 4. Bloated project should have findings and significant savings
    bloated_res = [r for r in results if r["target_name"] == "sample_bloated_project"][0]
    bloated_findings = len(bloated_res.get("quick_wins", [])) + len(bloated_res.get("worth_doing", [])) + len(bloated_res.get("optional", []))
    assert bloated_res["health_score"] < 90.0, f"Bloated project score should be < 90, got {bloated_res['health_score']}"
    assert bloated_findings > 0, f"Bloated project should have > 0 findings, got {bloated_findings}"
    assert bloated_res["total_savings_mb"] > 0.0, f"Bloated project savings should be > 0.0 MB, got {bloated_res['total_savings_mb']}"

    print("✓ All 3 distinct target assertions PASSED!")

if __name__ == "__main__":
    test_three_targets()
