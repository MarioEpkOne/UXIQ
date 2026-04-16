"""Tests for ui_analyzer.report_renderer — render() Markdown output."""
from __future__ import annotations

import pytest

from ui_analyzer.report_renderer import render
from ui_analyzer.scorer import Scores
from ui_analyzer.xml_parser import (
    AuditReport,
    Tier1Finding,
    Tier2Finding,
    Tier3Finding,
    Tier4Finding,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scores(t1=5.0, t2=5.0, t3=5.0, t4_count=0):
    return Scores(
        tier1=t1,
        tier2=t2,
        tier3=t3,
        tier4_flag_count=t4_count,
        overall=round(t1 * 0.4 + t2 * 0.35 + t3 * 0.25, 1),
    )


def _t1(result: str, estimated: bool = False) -> Tier1Finding:
    return Tier1Finding(
        criterion="1.4.3",
        element=".btn",
        result=result,
        estimated=estimated,
        observed="contrast 2.5:1",
        required="4.5:1",
        recommendation="darken text",
    )


def _t2(severity: int = 2) -> Tier2Finding:
    return Tier2Finding(
        principle="proximity",
        severity=severity,
        element="Card grid",
        issue="gap too small",
        recommendation="increase gap",
        nielsen_tag=4,
    )


def _t3(severity: int = 1) -> Tier3Finding:
    return Tier3Finding(
        principle="visual_hierarchy",
        severity=severity,
        element="CTA button",
        issue="not prominent",
        recommendation="increase size",
        nielsen_tag=8,
    )


def _t4() -> Tier4Finding:
    return Tier4Finding(
        pattern="data_ink_ratio",
        element="Sidebar",
        issue="icon-only nav",
        recommendation="add labels",
    )


def _render(report: AuditReport, **kwargs) -> str:
    defaults = dict(
        scores=_scores(),
        app_type="web_dashboard",
        image_source="/some/image.png",
        axe_succeeded=False,
        model="claude-sonnet-4-6",
    )
    defaults.update(kwargs)
    return render(report=report, **defaults)


# ---------------------------------------------------------------------------
# test_render_contains_all_tier_headers
# ---------------------------------------------------------------------------

def test_render_contains_all_tier_headers():
    """Rendered output contains all four tier section headers."""
    report = AuditReport()
    result = _render(report)

    assert "## Tier 1 — Accessibility" in result
    assert "## Tier 2 — Visual Structure" in result
    assert "## Tier 3 — Usability & Affordance" in result
    assert "## Tier 4 — Domain Patterns" in result


# ---------------------------------------------------------------------------
# test_render_fail_finding_has_red_x
# ---------------------------------------------------------------------------

def test_render_fail_finding_has_red_x():
    """Tier1Finding with result='FAIL' → ❌ present in rendered output."""
    report = AuditReport(tier1_findings=[_t1("FAIL")])
    result = _render(report)
    assert "❌" in result


# ---------------------------------------------------------------------------
# test_render_pass_finding_has_checkmark
# ---------------------------------------------------------------------------

def test_render_pass_finding_has_checkmark():
    """Tier1Finding with result='PASS' → ✅ present in rendered output."""
    report = AuditReport(tier1_findings=[_t1("PASS")])
    result = _render(report)
    assert "✅" in result


# ---------------------------------------------------------------------------
# test_render_estimated_label
# ---------------------------------------------------------------------------

def test_render_estimated_label():
    """Tier1Finding with estimated=True → 'ESTIMATED' present in rendered output."""
    report = AuditReport(tier1_findings=[_t1("FAIL", estimated=True)])
    result = _render(report)
    assert "ESTIMATED" in result


# ---------------------------------------------------------------------------
# test_render_empty_tier_shows_no_issues_found
# ---------------------------------------------------------------------------

def test_render_empty_tier_shows_no_issues_found():
    """AuditReport with empty tier2_findings → '*No issues found.*' in Tier 2 section."""
    report = AuditReport(tier2_findings=[])
    result = _render(report)
    # The renderer emits "*No issues found.*" inside the Tier 2 section
    assert "*No issues found.*" in result


# ---------------------------------------------------------------------------
# test_render_parse_warnings_appended
# ---------------------------------------------------------------------------

def test_render_parse_warnings_appended():
    """AuditReport with parse_warnings → warning block with '⚠️ Parse warning:' prefix present."""
    report = AuditReport(parse_warnings=["something went wrong"])
    result = _render(report)
    assert "⚠️ Parse warning:" in result


# ---------------------------------------------------------------------------
# test_render_tier4_flag_icon
# ---------------------------------------------------------------------------

def test_render_tier4_flag_icon():
    """Tier4Finding → '🚩' present in rendered output."""
    report = AuditReport(tier4_findings=[_t4()])
    result = _render(report, scores=_scores(t4_count=1))
    assert "🚩" in result


# ---------------------------------------------------------------------------
# test_render_severity_3_has_red_circle
# ---------------------------------------------------------------------------

def test_render_severity_3_has_red_circle():
    """Tier2Finding with severity=3 → '🔴' present in rendered output."""
    report = AuditReport(tier2_findings=[_t2(severity=3)])
    result = _render(report)
    assert "🔴" in result


# ---------------------------------------------------------------------------
# test_render_footer_contains_model
# ---------------------------------------------------------------------------

def test_render_footer_contains_model():
    """Rendered output ends with a line containing 'claude-sonnet-4-6'."""
    report = AuditReport()
    result = _render(report, model="claude-sonnet-4-6")
    assert "claude-sonnet-4-6" in result
    # Footer is the last line
    last_line = result.strip().split("\n")[-1]
    assert "claude-sonnet-4-6" in last_line


# ---------------------------------------------------------------------------
# test_render_with_parse_warnings_includes_warning_text
# ---------------------------------------------------------------------------

def test_render_with_parse_warnings_includes_warning_text():
    """Rendered output includes the actual warning text, not just a generic message."""
    report = AuditReport(parse_warnings=["No <audit_report> block found in response"])
    result = _render(report)
    assert "No <audit_report> block found in response" in result
