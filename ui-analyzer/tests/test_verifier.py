"""Tests for ui_analyzer.verifier.run_verification() — mocked API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from ui_analyzer.axe_runner import AxeCoreResult, AxeFailure
from ui_analyzer.dom_extractor import DomElements
from ui_analyzer.handler import analyze_ui_screenshot
from ui_analyzer.verifier import run_verification
from ui_analyzer.xml_parser import AuditReport, Tier1Finding


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_VALID_XML = """\
<audit_report>
  <confidence level="medium">Visible content assessed.</confidence>
  <inventory>Two buttons.</inventory>
  <structure_observation>Left-aligned layout.</structure_observation>
  <tier1_findings>
    <finding criterion="1.4.3" element=".nav-link" result="FAIL" estimated="false">
      <observed>contrast ratio 2.8:1</observed>
      <required>4.5:1 for normal text</required>
      <recommendation>Darken text</recommendation>
    </finding>
  </tier1_findings>
  <tier2_findings></tier2_findings>
  <tier3_findings></tier3_findings>
  <tier4_findings></tier4_findings>
</audit_report>
"""

VERIFIER_ASSESSMENT_ONLY = "<verification_report><assessment>Report verified. No amendments required.</assessment></verification_report>"

VERIFIER_WITH_REMOVE = """\
<verification_report>
  <tier1_amendments>
    <remove criterion="1.4.3" element=".nav-link">
      <reason>Finding not applicable to this screenshot</reason>
    </remove>
  </tier1_amendments>
</verification_report>
"""

_FAKE_IMAGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def _make_resolved_url():
    from ui_analyzer.image_source import ResolvedImage
    return ResolvedImage(bytes=_FAKE_IMAGE_BYTES, source_type="url", width_px=1280, height_px=800)


def _make_claude_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    resp = MagicMock()
    resp.content = [content_block]
    resp.stop_reason = "end_turn"
    return resp


# ---------------------------------------------------------------------------
# Test 1: verify=False → messages.create called exactly once
# ---------------------------------------------------------------------------

def test_verify_false_no_second_api_call(mocker):
    """verify=False → messages.create called exactly once (no verifier call)."""
    mocker.patch("ui_analyzer.handler.resolve", return_value=_make_resolved_url())
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeCoreResult(findings=[]))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")

    mock_anthropic = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_anthropic.return_value.messages.create.return_value = _make_claude_response(MINIMAL_VALID_XML)

    analyze_ui_screenshot("https://example.com", "web_dashboard", verify=False)

    assert mock_anthropic.return_value.messages.create.call_count == 1


# ---------------------------------------------------------------------------
# Test 2: verifier API timeout → original AuditReport returned, parse_warning added
# ---------------------------------------------------------------------------

def test_verifier_timeout_soft_fail():
    """Verifier APITimeoutError → original AuditReport unchanged; parse_warnings has timeout note."""
    client = MagicMock()
    client.messages.create.side_effect = anthropic.APITimeoutError(request=MagicMock())

    original = AuditReport(
        tier1_findings=[
            Tier1Finding(
                criterion="1.4.3", element=".nav", result="FAIL",
                estimated=False, observed="low", required="4.5:1", recommendation="fix",
            )
        ]
    )

    result = run_verification(
        client=client,
        system=[{"type": "text", "text": "sys"}],
        user_content=[{"type": "text", "text": "user"}],
        primary_raw_text="<audit_report/>",
        audit_report=original,
    )

    assert len(result.tier1_findings) == 1  # unchanged
    assert any("API timeout" in w for w in result.parse_warnings)


# ---------------------------------------------------------------------------
# Test 3: verifier rate limit → same soft fail as timeout
# ---------------------------------------------------------------------------

def test_verifier_rate_limit_soft_fail():
    """Verifier RateLimitError → original AuditReport unchanged; parse_warnings has timeout note."""
    client = MagicMock()
    client.messages.create.side_effect = anthropic.RateLimitError(
        message="rate limit", response=MagicMock(), body=None
    )

    original = AuditReport()

    result = run_verification(
        client=client,
        system=[],
        user_content=[],
        primary_raw_text="",
        audit_report=original,
    )

    assert any("API timeout" in w for w in result.parse_warnings)


# ---------------------------------------------------------------------------
# Test 4: clean verifier response with amendment → amended AuditReport returned
# ---------------------------------------------------------------------------

def test_verifier_applies_amendment():
    """Verifier returns a remove amendment → amended AuditReport has fewer findings."""
    client = MagicMock()
    client.messages.create.return_value = _make_claude_response(VERIFIER_WITH_REMOVE)

    original = AuditReport(
        tier1_findings=[
            Tier1Finding(
                criterion="1.4.3", element=".nav-link", result="FAIL",
                estimated=False, observed="low", required="4.5:1", recommendation="fix",
            )
        ]
    )

    result = run_verification(
        client=client,
        system=[],
        user_content=[],
        primary_raw_text=MINIMAL_VALID_XML,
        audit_report=original,
    )

    assert result.tier1_findings == []  # finding removed


# ---------------------------------------------------------------------------
# Test 5: verifier returns no-amendment assessment → AuditReport unchanged, no warnings
# ---------------------------------------------------------------------------

def test_verifier_no_amendments_unchanged():
    """Verifier assessment-only response → AuditReport unchanged, no parse_warnings."""
    client = MagicMock()
    client.messages.create.return_value = _make_claude_response(VERIFIER_ASSESSMENT_ONLY)

    original = AuditReport(
        tier1_findings=[
            Tier1Finding(
                criterion="1.4.3", element=".nav", result="FAIL",
                estimated=False, observed="low", required="4.5:1", recommendation="fix",
            )
        ]
    )

    result = run_verification(
        client=client,
        system=[],
        user_content=[],
        primary_raw_text=MINIMAL_VALID_XML,
        audit_report=original,
    )

    assert len(result.tier1_findings) == 1
    assert result.parse_warnings == []
