"""Tests for ui_analyzer.scorer — compute() and stars_to_display()."""
from __future__ import annotations

import pytest

from ui_analyzer.scorer import Scores, compute, stars_to_display
from ui_analyzer.xml_parser import AuditReport, Tier1Finding, Tier2Finding, Tier3Finding


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _t1(result: str) -> Tier1Finding:
    return Tier1Finding(
        criterion="1.4.3",
        element=".btn",
        result=result,
        estimated=False,
        observed="observed",
        required="required",
        recommendation="fix it",
    )


def _t23(severity: int) -> Tier2Finding:
    return Tier2Finding(
        principle="proximity",
        severity=severity,
        element="Card",
        issue="gap too small",
        recommendation="increase gap",
    )


def _t3(severity: int) -> Tier3Finding:
    return Tier3Finding(
        principle="visual_hierarchy",
        severity=severity,
        element="CTA",
        issue="not prominent",
        recommendation="increase size",
    )


def _report(
    tier1=None,
    tier2=None,
    tier3=None,
    tier4=None,
) -> AuditReport:
    return AuditReport(
        tier1_findings=tier1 or [],
        tier2_findings=tier2 or [],
        tier3_findings=tier3 or [],
        tier4_findings=tier4 or [],
    )


# ---------------------------------------------------------------------------
# Tier 1 scoring
# ---------------------------------------------------------------------------

def test_tier1_stars_all_pass():
    """All Tier 1 findings PASS → 5.0."""
    report = _report(tier1=[_t1("PASS"), _t1("PASS"), _t1("PASS")])
    scores = compute(report)
    assert scores.tier1 == 5.0


def test_tier1_stars_60_percent_pass():
    """3 PASS, 2 FAIL (60%) → 3.0."""
    findings = [_t1("PASS")] * 3 + [_t1("FAIL")] * 2
    report = _report(tier1=findings)
    scores = compute(report)
    assert scores.tier1 == 3.0


def test_tier1_stars_no_findings():
    """No Tier 1 findings → 5.0 (assume clean)."""
    report = _report(tier1=[])
    scores = compute(report)
    assert scores.tier1 == 5.0


# ---------------------------------------------------------------------------
# Tier 2/3 scoring
# ---------------------------------------------------------------------------

def test_tier23_stars_no_findings():
    """No Tier 2 findings → 5.0."""
    report = _report(tier2=[])
    scores = compute(report)
    assert scores.tier2 == 5.0


def test_tier23_stars_all_severity_3():
    """Two severity=3 findings → avg=3.0 → 5.0 - 3.0*1.5 = 0.5 → max(1.0, 0.5) = 1.0."""
    findings = [_t23(3), _t23(3)]
    report = _report(tier2=findings)
    scores = compute(report)
    assert scores.tier2 == 1.0


def test_tier23_stars_mixed():
    """severity=1 + severity=2 → avg=1.5 → 5.0 - 1.5*1.5 = 2.75 → round = 2.8."""
    findings = [_t23(1), _t23(2)]
    report = _report(tier2=findings)
    scores = compute(report)
    assert scores.tier2 == 2.8


# ---------------------------------------------------------------------------
# Overall weighting
# NOTE: spec prose says 4.1 but Python float gives 4.0 — see plan for explanation.
# ---------------------------------------------------------------------------

def test_overall_weighting():
    """T1=5.0, T2=3.5, T3=3.5 → overall = round(5.0*0.4 + 3.5*0.35 + 3.5*0.25, 1) = 4.1.

    Uses compute() end-to-end:
    - T1=5.0: no tier1 findings (empty list → 5 stars)
    - T2=3.5: one severity=1 tier2 finding → avg=1.0 → 5.0 - 1.0*1.5 = 3.5
    - T3=3.5: one severity=1 tier3 finding → avg=1.0 → 5.0 - 1.0*1.5 = 3.5
    - overall = round(2.0 + 1.225 + 0.875, 1) = 4.1
    """
    report = _report(
        tier1=[],
        tier2=[_t23(1)],
        tier3=[_t3(1)],
    )
    scores = compute(report)
    assert scores.tier1 == 5.0
    assert scores.tier2 == 3.5
    assert scores.tier3 == 3.5
    assert scores.overall == 4.1


# ---------------------------------------------------------------------------
# stars_to_display
# ---------------------------------------------------------------------------

def test_stars_to_display_3_1():
    """3.1 → '★★★☆☆' (rounds to 3 filled)."""
    assert stars_to_display(3.1) == "★★★☆☆"


def test_stars_to_display_5_0():
    """5.0 → '★★★★★'."""
    assert stars_to_display(5.0) == "★★★★★"


def test_stars_to_display_1_0():
    """1.0 → '★☆☆☆☆'."""
    assert stars_to_display(1.0) == "★☆☆☆☆"


# ---------------------------------------------------------------------------
# tier4_flag_count
# ---------------------------------------------------------------------------

def test_tier4_flag_count():
    """tier4_flag_count equals number of Tier 4 findings."""
    from ui_analyzer.xml_parser import Tier4Finding
    findings = [
        Tier4Finding(pattern="p1", element="e1", issue="i1", recommendation="r1"),
        Tier4Finding(pattern="p2", element="e2", issue="i2", recommendation="r2"),
    ]
    report = _report(tier4=findings)
    scores = compute(report)
    assert scores.tier4_flag_count == 2
