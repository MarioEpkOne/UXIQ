"""Tests for handler.py — analyze_ui_screenshot() orchestration.

All Playwright and Anthropic API calls are mocked.
Tests cover the 7 scenarios specified in Spec 08.
"""
from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from ui_analyzer.axe_runner import AxeCoreResult, AxeFailure
from ui_analyzer.exceptions import UIAnalyzerError
from ui_analyzer.handler import _media_type, _to_base64, analyze_ui_screenshot
from ui_analyzer.image_source import ResolvedImage
from ui_analyzer.xml_parser import AuditReport

_REAL_KEY = os.getenv("ANTHROPIC_API_KEY", "")
skip_if_no_key = pytest.mark.skipif(
    _REAL_KEY in ("", "test-key-unit-tests"),
    reason="ANTHROPIC_API_KEY not set to a real key",
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

MINIMAL_VALID_XML = """\
<audit_report>
  <confidence level="medium">Visible content assessed.</confidence>
  <inventory>Two buttons, one heading.</inventory>
  <structure_observation>Left-aligned layout.</structure_observation>
  <tier1_findings></tier1_findings>
  <tier2_findings></tier2_findings>
  <tier3_findings></tier3_findings>
  <tier4_findings></tier4_findings>
</audit_report>
"""

MALFORMED_XML = "Claude says: sorry, cannot produce XML today."

_FAKE_IMAGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # 108 bytes fake PNG


def _make_resolved_file() -> ResolvedImage:
    return ResolvedImage(
        bytes=_FAKE_IMAGE_BYTES,
        source_type="file",
        width_px=800,
        height_px=600,
    )


def _make_resolved_url() -> ResolvedImage:
    return ResolvedImage(
        bytes=_FAKE_IMAGE_BYTES,
        source_type="url",
        width_px=1280,
        height_px=800,
    )


def _make_claude_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    resp = MagicMock()
    resp.content = [content_block]
    return resp


# ---------------------------------------------------------------------------
# Scenario 1: valid file path → returns str with all four tier section headers
# ---------------------------------------------------------------------------

def test_valid_file_path_returns_markdown_with_all_tiers(fixtures_dir, mocker):
    """Valid file path → Markdown str containing all four tier section headers."""
    file_path = f"{fixtures_dir}/dashboard_good.png"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        MINIMAL_VALID_XML
    )

    result = analyze_ui_screenshot(file_path, "web_dashboard")

    assert isinstance(result, str)
    assert "## Tier 1" in result
    assert "## Tier 2" in result
    assert "## Tier 3" in result
    assert "## Tier 4" in result


# ---------------------------------------------------------------------------
# Scenario 2: valid URL → Tier 1 mode shows "Authoritative (axe-core)"
# ---------------------------------------------------------------------------

def test_valid_url_axe_success_shows_authoritative(mocker):
    """Valid URL with axe success → report header shows 'Authoritative (axe-core)'."""
    url = "https://example.com"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_url(),
    )
    mocker.patch(
        "ui_analyzer.handler.run_axe",
        return_value=AxeCoreResult(findings=[]),
    )
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        MINIMAL_VALID_XML
    )

    result = analyze_ui_screenshot(url, "landing_page")

    assert "Authoritative (axe-core)" in result


# ---------------------------------------------------------------------------
# Scenario 3: axe-core failure (mocked) → returns str with ESTIMATED labels, no exception
# ---------------------------------------------------------------------------

def test_axe_failure_returns_string_not_exception(mocker):
    """AxeFailure from run_axe → report returned (no exception), ESTIMATED mode."""
    url = "https://example.com"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_url(),
    )
    mocker.patch(
        "ui_analyzer.handler.run_axe",
        return_value=AxeFailure(reason="axe-core JS injection failed"),
    )
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        MINIMAL_VALID_XML
    )

    result = analyze_ui_screenshot(url, "forms")

    assert isinstance(result, str)
    # axe_succeeded=False → renderer uses "Estimated (visual)"
    assert "Estimated (visual)" in result


# ---------------------------------------------------------------------------
# Scenario 4: malformed XML from Claude → returns str with warning, no exception
# ---------------------------------------------------------------------------

def test_malformed_xml_returns_string_with_warning(fixtures_dir, mocker):
    """Malformed XML from Claude → report str returned with parse warning block."""
    file_path = f"{fixtures_dir}/form.png"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        MALFORMED_XML
    )

    result = analyze_ui_screenshot(file_path, "onboarding_flow")

    assert isinstance(result, str)
    # render() adds a warning block when parse_warnings is non-empty
    assert "malformed" in result.lower() or "warning" in result.lower() or "⚠️" in result


# ---------------------------------------------------------------------------
# Scenario 5: API timeout (mocked) → raises UIAnalyzerError
# ---------------------------------------------------------------------------

def test_api_timeout_raises_ui_analyzer_error(fixtures_dir, mocker):
    """APITimeoutError from Claude → UIAnalyzerError raised."""
    import anthropic as _anthropic

    file_path = f"{fixtures_dir}/dashboard_bad.png"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.side_effect = _anthropic.APITimeoutError(
        request=MagicMock()
    )

    with pytest.raises(UIAnalyzerError, match="timed out"):
        analyze_ui_screenshot(file_path, "web_dashboard")


# ---------------------------------------------------------------------------
# Scenario 6: API rate limit (mocked) → raises UIAnalyzerError
# ---------------------------------------------------------------------------

def test_api_rate_limit_raises_ui_analyzer_error(fixtures_dir, mocker):
    """RateLimitError from Claude → UIAnalyzerError raised."""
    import anthropic as _anthropic

    file_path = f"{fixtures_dir}/landing_page.png"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.side_effect = _anthropic.RateLimitError(
        message="rate limit", response=MagicMock(), body=None
    )

    with pytest.raises(UIAnalyzerError, match="rate limit"):
        analyze_ui_screenshot(file_path, "landing_page")


# ---------------------------------------------------------------------------
# Scenario 7: invalid app_type → Pydantic ValidationError before any API/Playwright call
# ---------------------------------------------------------------------------

def test_invalid_app_type_raises_validation_error_before_any_io(mocker):
    """Invalid app_type → Pydantic ValidationError raised; resolve() never called."""
    mock_resolve = mocker.patch("ui_analyzer.handler.resolve")

    with pytest.raises(ValidationError):
        analyze_ui_screenshot("/some/path.png", "not_a_valid_type")

    mock_resolve.assert_not_called()


# ---------------------------------------------------------------------------
# Unit tests for private helpers
# ---------------------------------------------------------------------------

def test_to_base64_roundtrips():
    data = b"hello world"
    encoded = _to_base64(data)
    assert base64.b64decode(encoded) == data


def test_media_type_url_always_png():
    assert _media_type("https://example.com") == "image/png"
    assert _media_type("http://example.com/page") == "image/png"


def test_media_type_jpg():
    assert _media_type("/path/to/shot.jpg") == "image/jpeg"
    assert _media_type("/path/to/shot.jpeg") == "image/jpeg"
    assert _media_type("/PATH/TO/SHOT.JPG") == "image/jpeg"


def test_media_type_webp():
    assert _media_type("/path/to/shot.webp") == "image/webp"


def test_media_type_png_and_default():
    assert _media_type("/path/to/shot.png") == "image/png"
    assert _media_type("/path/to/shot.bmp") == "image/png"  # default


# ---------------------------------------------------------------------------
# Scenario (unit): non-UI preamble is passed through without raising
# ---------------------------------------------------------------------------

def test_handler_non_ui_preamble_passes_through(fixtures_dir, mocker):
    """Claude response with non-UI preamble followed by valid XML → str returned, no exception."""
    NON_UI_PREAMBLE_XML = (
        "⚠️ The provided image does not appear to be a web UI screenshot.\n\n"
        + MINIMAL_VALID_XML
    )

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        NON_UI_PREAMBLE_XML
    )

    result = analyze_ui_screenshot(f"{fixtures_dir}/dashboard_good.png", "web_dashboard")

    assert isinstance(result, str)
    assert "⚠️ The provided image does not appear to be a web UI" in result
    assert "## Tier 1" in result


# ---------------------------------------------------------------------------
# Unit: no preamble → output starts with "# UI Analysis Report" (no leading blank lines)
# ---------------------------------------------------------------------------

def test_handler_no_preamble_output_unchanged(fixtures_dir, mocker):
    """Response starting directly with <audit_report> → output is unchanged (no extra whitespace prepended)."""
    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        MINIMAL_VALID_XML
    )

    result = analyze_ui_screenshot(f"{fixtures_dir}/dashboard_good.png", "web_dashboard")

    assert result.startswith("# UI Analysis Report")


# ---------------------------------------------------------------------------
# Unit: whitespace-only preamble → suppressed, output starts with "# UI Analysis Report"
# ---------------------------------------------------------------------------

def test_handler_whitespace_only_preamble_not_prepended(fixtures_dir, mocker):
    """Response with whitespace-only text before <audit_report> → preamble suppressed."""
    WHITESPACE_PREAMBLE_XML = "   \n\n" + MINIMAL_VALID_XML

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        WHITESPACE_PREAMBLE_XML
    )

    result = analyze_ui_screenshot(f"{fixtures_dir}/dashboard_good.png", "web_dashboard")

    assert result.startswith("# UI Analysis Report")


# ---------------------------------------------------------------------------
# Unit: no <audit_report> at all → entire response is preamble; malformed warning also shown
# ---------------------------------------------------------------------------

def test_handler_no_xml_preamble_shown(fixtures_dir, mocker):
    """Response with no <audit_report> tag → entire response used as preamble; malformed warning present."""
    NO_XML_RESPONSE = "I cannot analyze this image."

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        NO_XML_RESPONSE
    )

    result = analyze_ui_screenshot(f"{fixtures_dir}/dashboard_good.png", "web_dashboard")

    assert result.startswith("I cannot analyze this image.")
    assert "⚠️" in result or "malformed" in result.lower() or "warning" in result.lower()


# ---------------------------------------------------------------------------
# Integration tests — require a real ANTHROPIC_API_KEY
# ---------------------------------------------------------------------------

@pytest.mark.integration
@skip_if_no_key
def test_full_analysis_file_path(fixtures_dir):
    """Integration: real API call with dashboard_good.png → all four tier headers present."""
    import pathlib
    result = analyze_ui_screenshot(
        str(pathlib.Path(fixtures_dir) / "dashboard_good.png"), "web_dashboard"
    )
    assert isinstance(result, str)
    assert "## Tier 1" in result
    assert "## Tier 2" in result
    assert "## Tier 3" in result
    assert "## Tier 4" in result


@pytest.mark.integration
@skip_if_no_key
def test_full_analysis_url():
    """Integration: real URL analysis → 'Authoritative (axe-core)' in report."""
    result = analyze_ui_screenshot("https://example.com", "web_dashboard")
    assert isinstance(result, str)
    assert "Authoritative (axe-core)" in result


@pytest.mark.integration
@skip_if_no_key
def test_non_ui_image(fixtures_dir):
    """Integration: non-UI image → str returned, no exception."""
    import pathlib
    result = analyze_ui_screenshot(
        str(pathlib.Path(fixtures_dir) / "not_a_ui.jpg"), "landing_page"
    )
    assert isinstance(result, str)  # Does not raise


@pytest.mark.integration
@skip_if_no_key
def test_app_type_forms(fixtures_dir):
    """Integration: forms app_type → report header contains 'Tier 4 — Domain Patterns (forms)'."""
    import pathlib
    result = analyze_ui_screenshot(
        str(pathlib.Path(fixtures_dir) / "form.png"), "forms"
    )
    assert isinstance(result, str)
    assert "## Tier 4 — Domain Patterns (forms)" in result
