"""Tests for handler.py — analyze_ui_screenshot() orchestration.

All Playwright and Anthropic API calls are mocked.
Tests cover the 7 scenarios specified in Spec 08.
"""
from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from ui_analyzer.axe_runner import AxeCoreResult, AxeFailure
from ui_analyzer.dom_extractor import DomElements, DomFailure
from ui_analyzer.exceptions import UIAnalyzerError
from ui_analyzer.handler import _extract_preamble, _media_type, _to_base64, analyze_ui_screenshot
from ui_analyzer.image_source import ResolvedImage
from ui_analyzer.xml_parser import AuditReport


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


def _make_usage() -> MagicMock:
    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 200
    usage.cache_creation_input_tokens = 50
    usage.cache_read_input_tokens = 0
    return usage


def _make_claude_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    resp = MagicMock()
    resp.content = [content_block]
    resp.stop_reason = "end_turn"
    resp.usage = _make_usage()
    return resp


# ---------------------------------------------------------------------------
# Scenario 1: valid file path → returns str with all four tier section headers
# ---------------------------------------------------------------------------

def test_valid_file_path_returns_markdown_with_all_tiers(mocker):
    """Valid URL → Markdown str containing all four tier section headers."""
    url = "https://example.com"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_url(),
    )
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeCoreResult(findings=[]))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        MINIMAL_VALID_XML
    )

    result = analyze_ui_screenshot(url, "web_dashboard")

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
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")
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
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")
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

def test_malformed_xml_returns_string_with_warning(mocker):
    """Malformed XML from Claude → report str returned with parse warning block."""
    url = "https://example.com"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_url(),
    )
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeCoreResult(findings=[]))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        MALFORMED_XML
    )

    result = analyze_ui_screenshot(url, "onboarding_flow")

    assert isinstance(result, str)
    # render() adds a warning block when parse_warnings is non-empty
    assert "malformed" in result.lower() or "warning" in result.lower() or "⚠️" in result


# ---------------------------------------------------------------------------
# Scenario 5: API timeout (mocked) → raises UIAnalyzerError
# ---------------------------------------------------------------------------

def test_api_timeout_raises_ui_analyzer_error(mocker):
    """APITimeoutError from Claude → UIAnalyzerError raised."""
    import anthropic as _anthropic

    url = "https://example.com"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_url(),
    )
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeCoreResult(findings=[]))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.side_effect = _anthropic.APITimeoutError(
        request=MagicMock()
    )

    with pytest.raises(UIAnalyzerError, match="timed out"):
        analyze_ui_screenshot(url, "web_dashboard")


# ---------------------------------------------------------------------------
# Scenario 6: API rate limit (mocked) → raises UIAnalyzerError
# ---------------------------------------------------------------------------

def test_api_rate_limit_raises_ui_analyzer_error(mocker):
    """RateLimitError from Claude → UIAnalyzerError raised."""
    import anthropic as _anthropic

    url = "https://example.com"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_url(),
    )
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeCoreResult(findings=[]))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.side_effect = _anthropic.RateLimitError(
        message="rate limit", response=MagicMock(), body=None
    )

    with pytest.raises(UIAnalyzerError, match="rate limit"):
        analyze_ui_screenshot(url, "landing_page")


# ---------------------------------------------------------------------------
# Scenario: file path input → pydantic.ValidationError before any IO
# ---------------------------------------------------------------------------

def test_file_path_raises_validation_error(mocker):
    """File path input → pydantic.ValidationError raised; resolve() never called."""
    mock_resolve = mocker.patch("ui_analyzer.handler.resolve")

    with pytest.raises(ValidationError, match="must be a URL"):
        analyze_ui_screenshot("/some/path/screenshot.png", "web_dashboard")

    mock_resolve.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario 7: invalid app_type → Pydantic ValidationError before any API/Playwright call
# ---------------------------------------------------------------------------

def test_invalid_app_type_raises_validation_error_before_any_io(mocker):
    """Invalid app_type → Pydantic ValidationError raised; resolve() never called."""
    mock_resolve = mocker.patch("ui_analyzer.handler.resolve")

    with pytest.raises(ValidationError):
        analyze_ui_screenshot("https://example.com", "not_a_valid_type")

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

def test_handler_non_ui_preamble_passes_through(mocker):
    """Claude response with non-UI preamble followed by valid XML → str returned, no exception."""
    NON_UI_PREAMBLE_XML = (
        "⚠️ The provided image does not appear to be a web UI screenshot.\n\n"
        + MINIMAL_VALID_XML
    )

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_url(),
    )
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeCoreResult(findings=[]))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")
    mock_create = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        NON_UI_PREAMBLE_XML
    )

    result = analyze_ui_screenshot("https://example.com", "web_dashboard")

    assert isinstance(result, str)
    assert "⚠️ The provided image does not appear to be a web UI" in result
    assert "## Tier 1" in result


# ---------------------------------------------------------------------------
# Unit: no preamble → output starts with "# UI Analysis Report" (no leading blank lines)
# ---------------------------------------------------------------------------

def test_handler_no_preamble_output_unchanged(mocker):
    """Response starting directly with <audit_report> → output is unchanged (no extra whitespace prepended)."""
    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_url(),
    )
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeCoreResult(findings=[]))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")
    mock_create = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        MINIMAL_VALID_XML
    )

    result = analyze_ui_screenshot("https://example.com", "web_dashboard")

    assert result.startswith("# UI Analysis Report")


# ---------------------------------------------------------------------------
# Unit: whitespace-only preamble → suppressed, output starts with "# UI Analysis Report"
# ---------------------------------------------------------------------------

def test_handler_whitespace_only_preamble_not_prepended(mocker):
    """Response with whitespace-only text before <audit_report> → preamble suppressed."""
    WHITESPACE_PREAMBLE_XML = "   \n\n" + MINIMAL_VALID_XML

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_url(),
    )
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeCoreResult(findings=[]))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")
    mock_create = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        WHITESPACE_PREAMBLE_XML
    )

    result = analyze_ui_screenshot("https://example.com", "web_dashboard")

    assert result.startswith("# UI Analysis Report")


# ---------------------------------------------------------------------------
# Unit: no <audit_report> at all → entire response is preamble; malformed warning also shown
# ---------------------------------------------------------------------------

def test_handler_no_xml_preamble_shown(mocker):
    """Response with no <audit_report> tag → entire response used as preamble; malformed warning present."""
    NO_XML_RESPONSE = "I cannot analyze this image."

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_url(),
    )
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeCoreResult(findings=[]))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")
    mock_create = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        NO_XML_RESPONSE
    )

    result = analyze_ui_screenshot("https://example.com", "web_dashboard")

    assert result.startswith("I cannot analyze this image.")
    assert "⚠️" in result or "malformed" in result.lower() or "warning" in result.lower()


# ---------------------------------------------------------------------------
# Progress callback tests
# ---------------------------------------------------------------------------

def test_progress_callbacks_called_in_order_with_correct_stage_ids(mocker):
    """analyze_ui_screenshot with a mock progress → stage_start/stage_end called in expected order."""
    from unittest.mock import call, MagicMock as MM

    url = "https://example.com"
    mocker.patch("ui_analyzer.handler.resolve", return_value=_make_resolved_url())
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeCoreResult(findings=[]))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")
    mock_client = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_client.return_value.messages.create.return_value = _make_claude_response(MINIMAL_VALID_XML)

    mock_progress = MM()

    analyze_ui_screenshot(url, "web_dashboard", progress=mock_progress)

    # Extract only stage_start calls (in order)
    start_calls = [c for c in mock_progress.method_calls if c[0] == "stage_start"]
    end_calls = [c for c in mock_progress.method_calls if c[0] == "stage_end"]

    start_ids = [c[1][0] for c in start_calls]
    end_ids = [c[1][0] for c in end_calls]

    # All four stages should appear
    assert start_ids == ["image", "axe", "claude", "verify"]
    assert end_ids == ["image", "axe", "claude", "verify"]


def test_progress_not_called_when_none(mocker):
    """analyze_ui_screenshot with progress=None → no AttributeError; runs normally."""
    url = "https://example.com"
    mocker.patch("ui_analyzer.handler.resolve", return_value=_make_resolved_url())
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeCoreResult(findings=[]))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")
    mock_client = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_client.return_value.messages.create.return_value = _make_claude_response(MINIMAL_VALID_XML)

    # Should not raise
    result = analyze_ui_screenshot(url, "web_dashboard", progress=None)
    assert isinstance(result, str)


def test_progress_axe_failure_still_calls_stage_end(mocker):
    """AxeFailure → axe stage_end is still called with empty detail string."""
    from unittest.mock import MagicMock as MM

    url = "https://example.com"
    mocker.patch("ui_analyzer.handler.resolve", return_value=_make_resolved_url())
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeFailure(reason="injection failed"))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")
    mock_client = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_client.return_value.messages.create.return_value = _make_claude_response(MINIMAL_VALID_XML)

    mock_progress = MM()
    analyze_ui_screenshot(url, "web_dashboard", progress=mock_progress)

    axe_end_calls = [c for c in mock_progress.method_calls if c[0] == "stage_end" and c[1][0] == "axe"]
    assert len(axe_end_calls) == 1
    # detail should be empty string on axe failure
    _, pos_args, kw_args = axe_end_calls[0]
    detail = kw_args.get("detail", pos_args[3] if len(pos_args) > 3 else "")
    assert detail == ""


def test_progress_verify_false_skips_verify_stage(mocker):
    """verify=False → stage_start/stage_end for 'verify' are never called."""
    from unittest.mock import MagicMock as MM

    url = "https://example.com"
    mocker.patch("ui_analyzer.handler.resolve", return_value=_make_resolved_url())
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeCoreResult(findings=[]))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")
    mock_client = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_client.return_value.messages.create.return_value = _make_claude_response(MINIMAL_VALID_XML)

    mock_progress = MM()
    analyze_ui_screenshot(url, "web_dashboard", verify=False, progress=mock_progress)

    verify_calls = [c for c in mock_progress.method_calls if c[1] and c[1][0] == "verify"]
    assert verify_calls == []


def test_progress_elapsed_is_non_negative(mocker):
    """stage_end elapsed argument is always >= 0.0."""
    from unittest.mock import MagicMock as MM

    url = "https://example.com"
    mocker.patch("ui_analyzer.handler.resolve", return_value=_make_resolved_url())
    mocker.patch("ui_analyzer.handler.run_axe", return_value=AxeCoreResult(findings=[]))
    mocker.patch("ui_analyzer.handler.extract_dom", return_value=DomElements(elements=[]))
    mocker.patch("ui_analyzer.handler.write_run")
    mock_client = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_client.return_value.messages.create.return_value = _make_claude_response(MINIMAL_VALID_XML)

    mock_progress = MM()
    analyze_ui_screenshot(url, "web_dashboard", progress=mock_progress)

    end_calls = [c for c in mock_progress.method_calls if c[0] == "stage_end"]
    for call in end_calls:
        elapsed = call[1][2]  # third positional arg
        assert elapsed >= 0.0


# ---------------------------------------------------------------------------
# Tests for _is_image_url (Fix Group 1, D1/D2)
# ---------------------------------------------------------------------------

def test_is_image_url_detects_common_extensions():
    """Known image extensions (.png, .jpg, .gif, .webp, .svg, .ico) → True."""
    from ui_analyzer.handler import _is_image_url
    assert _is_image_url("https://example.com/image.png") is True
    assert _is_image_url("https://example.com/photo.jpg") is True
    assert _is_image_url("https://example.com/photo.jpeg") is True
    assert _is_image_url("https://example.com/anim.gif") is True
    assert _is_image_url("https://example.com/banner.webp") is True
    assert _is_image_url("https://example.com/logo.svg") is True
    assert _is_image_url("https://example.com/favicon.ico") is True


def test_is_image_url_uppercase_extension():
    """Uppercase extension (.PNG) → True (case-insensitive)."""
    from ui_analyzer.handler import _is_image_url
    assert _is_image_url("https://example.com/image.PNG") is True


def test_is_image_url_extension_before_query_string():
    """.png before query string → True (path check ignores query)."""
    from ui_analyzer.handler import _is_image_url
    assert _is_image_url("https://example.com/img.png?v=2&token=abc") is True


def test_is_image_url_path_segment_with_extension_word():
    """Path ending in '-editor' (not '.png') → False even if 'png' appears mid-path."""
    from ui_analyzer.handler import _is_image_url
    assert _is_image_url("https://app.example.com/png-editor") is False


def test_is_image_url_regular_page():
    """Dashboard URL with no image extension → False."""
    from ui_analyzer.handler import _is_image_url
    assert _is_image_url("https://app.example.com/dashboard") is False


# ---------------------------------------------------------------------------
# Tests for _check_ssrf (Fix Group 1, D4/D5/D6)
# ---------------------------------------------------------------------------

def test_check_ssrf_loopback_raises(mocker):
    """Hostname resolving to 127.0.0.1 → UIAnalyzerError."""
    from ui_analyzer.handler import _check_ssrf
    mocker.patch("ui_analyzer.handler.socket.gethostbyname", return_value="127.0.0.1")

    with pytest.raises(UIAnalyzerError, match="blocked"):
        _check_ssrf("https://internal.example.com/page")


def test_check_ssrf_private_network_raises(mocker):
    """Hostname resolving to 10.0.0.5 (RFC-1918) → UIAnalyzerError."""
    from ui_analyzer.handler import _check_ssrf
    mocker.patch("ui_analyzer.handler.socket.gethostbyname", return_value="10.0.0.5")

    with pytest.raises(UIAnalyzerError, match="blocked"):
        _check_ssrf("https://corp.example.com/api")


def test_check_ssrf_imds_raises(mocker):
    """Hostname resolving to 169.254.169.254 (AWS IMDS) → UIAnalyzerError."""
    from ui_analyzer.handler import _check_ssrf
    mocker.patch("ui_analyzer.handler.socket.gethostbyname", return_value="169.254.169.254")

    with pytest.raises(UIAnalyzerError, match="blocked"):
        _check_ssrf("https://metadata.internal/latest")


def test_check_ssrf_dns_failure_raises(mocker):
    """DNS resolution failure → UIAnalyzerError with 'Cannot resolve hostname'."""
    import socket as _socket
    from ui_analyzer.handler import _check_ssrf
    mocker.patch(
        "ui_analyzer.handler.socket.gethostbyname",
        side_effect=_socket.gaierror("Name or service not known"),
    )

    with pytest.raises(UIAnalyzerError, match="Cannot resolve hostname"):
        _check_ssrf("https://nonexistent.invalid/page")


def test_check_ssrf_public_ip_does_not_raise(mocker):
    """Hostname resolving to a public IP → no error raised."""
    from ui_analyzer.handler import _check_ssrf
    mocker.patch("ui_analyzer.handler.socket.gethostbyname", return_value="93.184.216.34")

    # Should not raise
    _check_ssrf("https://example.com/page")


# ---------------------------------------------------------------------------
# _extract_preamble — attributed tag regression tests (Bug 1 fix)
# ---------------------------------------------------------------------------

def test_extract_preamble_attributed_tag():
    """_extract_preamble() with attributed <audit_report version="1"> returns text before the tag."""
    raw = 'Here is my analysis.\n\n<audit_report version="1"><tier1_findings/></audit_report>'
    preamble = _extract_preamble(raw)
    assert preamble == "Here is my analysis."


def test_extract_preamble_plain_tag():
    """_extract_preamble() with plain <audit_report> — no regression from existing behavior."""
    raw = "Preamble text.\n\n<audit_report><tier1_findings/></audit_report>"
    preamble = _extract_preamble(raw)
    assert preamble == "Preamble text."
