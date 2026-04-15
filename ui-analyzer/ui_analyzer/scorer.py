"""scorer.py — Compute per-tier star ratings and overall weighted score.

Pure, deterministic. Does not call any API. Never raises.
"""

from __future__ import annotations

from dataclasses import dataclass

from ui_analyzer.xml_parser import AuditReport


@dataclass
class Scores:
    tier1: float            # 1.0–5.0
    tier2: float            # 1.0–5.0
    tier3: float            # 1.0–5.0
    tier4_flag_count: int   # count only — not scored
    overall: float          # weighted: T1×0.4 + T2×0.35 + T3×0.25


def compute(report: AuditReport) -> Scores:
    """Compute Scores from an AuditReport. Always returns Scores, never raises."""
    t1 = _compute_tier1_stars(report.tier1_findings)
    t2 = _compute_tier23_stars(report.tier2_findings)
    t3 = _compute_tier23_stars(report.tier3_findings)
    overall = round((t1 * 0.4) + (t2 * 0.35) + (t3 * 0.25), 1)
    return Scores(
        tier1=t1,
        tier2=t2,
        tier3=t3,
        tier4_flag_count=len(report.tier4_findings),
        overall=overall,
    )


def _compute_tier1_stars(findings) -> float:
    """% of Tier 1 checks that passed, mapped to 1–5 stars.

    100% = 5★, 80% = 4★, 60% = 3★, 40% = 2★, <40% = 1★
    No findings → 5★ (assume clean).
    """
    if not findings:
        return 5.0
    passes = sum(1 for f in findings if f.result == "PASS")
    total = len(findings)
    ratio = passes / total
    return max(1.0, round(ratio * 5, 1))


def _compute_tier23_stars(findings) -> float:
    """Avg severity inverted to stars.

    avg=0 → 5★, avg=1 → 4★, avg=2 → 2.5★, avg=3 → 1★
    No findings → 5★ (no issues found).
    """
    if not findings:
        return 5.0
    severities = [f.severity for f in findings if isinstance(f.severity, int)]
    if not severities:
        return 5.0
    avg = sum(severities) / len(severities)
    return max(1.0, round(5.0 - (avg * 1.5), 1))


def stars_to_display(score: float) -> str:
    """Convert a 1.0–5.0 score to a Unicode star string.

    E.g. 3.1 → "★★★☆☆"
    Rounds to nearest whole star for display.
    """
    filled = round(score)
    return "★" * filled + "☆" * (5 - filled)
