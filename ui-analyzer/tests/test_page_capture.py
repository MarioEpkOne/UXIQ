"""Tests for ui_analyzer.page_capture — unified Playwright capture."""
from __future__ import annotations

import pathlib
from unittest.mock import MagicMock, patch

import pytest

from ui_analyzer.axe_runner import AxeCoreResult
from ui_analyzer.dom_extractor import DomElement
from ui_analyzer.exceptions import UIAnalyzerError
from ui_analyzer.page_capture import PageCapture, capture_page


# ---------------------------------------------------------------------------
# Mock infrastructure
# ---------------------------------------------------------------------------

_FAKE_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

_FAKE_DOM_ELEMENTS = [
    {
        "tag": "button", "role": "", "text": "Sign up",
        "aria_label": "", "placeholder": "", "input_type": "",
        "alt": "", "x": 16, "y": 120, "w": 120, "h": 40,
    },
    {
        "tag": "img", "role": "", "text": "",
        "aria_label": "", "placeholder": "", "input_type": "",
        "alt": "logo", "x": 8, "y": 4, "w": 64, "h": 64,
    },
]

_FAKE_AXE_RAW = {"violations": [], "passes": [], "inapplicable": []}


def _make_mock_pw(
    *,
    goto_raises: Exception | None = None,
    goto_response_status: int | None = None,
    fonts_raises: Exception | None = None,
    screenshot_raises: Exception | None = None,
    dom_eval_raises: Exception | None = None,
    axe_inject_raises: Exception | None = None,
    axe_run_raises: Exception | None = None,
    dom_eval_result: list | None = None,
    axe_run_result: dict | None = None,
):
    """Build a nested mock for sync_playwright with targeted failure points.

    The mock routes page.evaluate calls to different behaviors depending on
    call order: (fonts -> dom -> axe_run). page.add_script_tag is separately
    configurable via axe_inject_raises.
    """
    mock_page = MagicMock()

    if goto_raises is not None:
        mock_page.goto.side_effect = goto_raises
    else:
        response = MagicMock()
        response.status = goto_response_status if goto_response_status is not None else 200
        mock_page.goto.return_value = response

    if screenshot_raises is not None:
        mock_page.screenshot.side_effect = screenshot_raises
    else:
        mock_page.screenshot.return_value = _FAKE_PNG_BYTES

    if axe_inject_raises is not None:
        mock_page.add_script_tag.side_effect = axe_inject_raises
    else:
        mock_page.add_script_tag.return_value = None

    # page.evaluate is called 3 times in order: fonts.ready, DOM JS, axe run.
    # Simulate each via side_effect.
    call_script = []
    if fonts_raises is not None:
        call_script.append(fonts_raises)
    else:
        call_script.append(None)  # fonts.ready resolves

    if dom_eval_raises is not None:
        call_script.append(dom_eval_raises)
    else:
        call_script.append(dom_eval_result if dom_eval_result is not None else _FAKE_DOM_ELEMENTS)

    if axe_run_raises is not None:
        call_script.append(axe_run_raises)
    else:
        call_script.append(axe_run_result if axe_run_result is not None else _FAKE_AXE_RAW)

    def _evaluate(*args, **kwargs):
        item = call_script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    mock_page.evaluate.side_effect = _evaluate
    mock_page.wait_for_timeout.return_value = None

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw_instance = MagicMock()
    mock_pw_instance.chromium.launch.return_value = mock_browser

    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_pw_instance)
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


# ---------------------------------------------------------------------------
# Unit tests (mocked Playwright)
# ---------------------------------------------------------------------------

def test_capture_page_happy_path(mocker):
    """All steps succeed → PageCapture populated with the mocked fixtures."""
    mock_cm = _make_mock_pw()
    mocker.patch("ui_analyzer.page_capture.sync_playwright", return_value=mock_cm)

    result = capture_page("https://example.com")

    assert isinstance(result, PageCapture)
    assert result.image_bytes == _FAKE_PNG_BYTES
    assert result.image_width_px == 1280
    assert result.image_height_px == 800
    assert isinstance(result.axe_result, AxeCoreResult)
    assert len(result.dom_elements) == 2
    btn = result.dom_elements[0]
    assert isinstance(btn, DomElement)
    assert btn.tag == "button"
    assert btn.text == "Sign up"
    assert btn.x == 16 and btn.y == 120 and btn.w == 120 and btn.h == 40
    img = result.dom_elements[1]
    assert img.tag == "img"
    assert img.alt == "logo"


def test_capture_page_goto_timeout_raises(mocker):
    """Playwright TimeoutError on goto → UIAnalyzerError prefixed with 'capture failed at goto'."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    mock_cm = _make_mock_pw(goto_raises=PlaywrightTimeout("timed out"))
    mocker.patch("ui_analyzer.page_capture.sync_playwright", return_value=mock_cm)

    with pytest.raises(UIAnalyzerError, match="capture failed at goto"):
        capture_page("https://slow.example.com")


def test_capture_page_goto_http_error_raises(mocker):
    """goto returns HTTP 404 → UIAnalyzerError mentioning the status."""
    mock_cm = _make_mock_pw(goto_response_status=404)
    mocker.patch("ui_analyzer.page_capture.sync_playwright", return_value=mock_cm)

    with pytest.raises(UIAnalyzerError, match="capture failed at goto: HTTP 404"):
        capture_page("https://example.com/missing")


def test_capture_page_fonts_timeout_is_soft(mocker, caplog):
    """fonts.ready timing out does NOT raise — it logs a warning and proceeds."""
    import logging
    caplog.set_level(logging.WARNING, logger="ui_analyzer.page_capture")
    mock_cm = _make_mock_pw(fonts_raises=RuntimeError("fonts timeout"))
    mocker.patch("ui_analyzer.page_capture.sync_playwright", return_value=mock_cm)

    result = capture_page("https://example.com")

    assert isinstance(result, PageCapture)
    # The helper recorded one warning for the fonts.ready failure.
    assert any("fonts" in r.message.lower() for r in caplog.records)


def test_capture_page_screenshot_failure_raises(mocker):
    """screenshot exception → UIAnalyzerError prefixed with 'capture failed at screenshot'."""
    mock_cm = _make_mock_pw(screenshot_raises=RuntimeError("screenshot unavailable"))
    mocker.patch("ui_analyzer.page_capture.sync_playwright", return_value=mock_cm)

    with pytest.raises(UIAnalyzerError, match="capture failed at screenshot"):
        capture_page("https://example.com")


@pytest.mark.parametrize(
    "failure_kwargs,match_prefix",
    [
        ({"dom_eval_raises": RuntimeError("JS destroyed")}, "capture failed at dom"),
        ({"axe_inject_raises": RuntimeError("CDN failure")}, "capture failed at axe_inject"),
        ({"axe_run_raises": RuntimeError("axe-core timed out")}, "capture failed at axe_run"),
    ],
)
def test_capture_page_substep_failures_are_attributed(mocker, failure_kwargs, match_prefix):
    """Each sub-step failure produces a UIAnalyzerError with the matching attribution."""
    mock_cm = _make_mock_pw(**failure_kwargs)
    mocker.patch("ui_analyzer.page_capture.sync_playwright", return_value=mock_cm)

    with pytest.raises(UIAnalyzerError, match=match_prefix):
        capture_page("https://example.com")


def test_capture_page_dom_elements_dataclass_round_trip(mocker):
    """DomElement construction handles all 11 fields from the raw JS payload."""
    raw_with_all_fields = [{
        "tag": "input", "role": "textbox", "text": "",
        "aria_label": "Email", "placeholder": "you@example.com", "input_type": "email",
        "alt": "", "x": 16, "y": 200, "w": 240, "h": 32,
    }]
    mock_cm = _make_mock_pw(dom_eval_result=raw_with_all_fields)
    mocker.patch("ui_analyzer.page_capture.sync_playwright", return_value=mock_cm)

    result = capture_page("https://example.com")

    el = result.dom_elements[0]
    assert el.tag == "input"
    assert el.role == "textbox"
    assert el.aria_label == "Email"
    assert el.placeholder == "you@example.com"
    assert el.input_type == "email"
    assert (el.x, el.y, el.w, el.h) == (16, 200, 240, 32)


# ---------------------------------------------------------------------------
# Integration tests (real Chromium against a file:// fixture)
# ---------------------------------------------------------------------------

def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False


_FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "sample_page.html"
_FIXTURE_URL = _FIXTURE_PATH.as_uri()

pytestmark_chromium = pytest.mark.skipif(
    not _chromium_available(),
    reason="Chromium browser not installed for Playwright; run `playwright install chromium`.",
)


@pytest.mark.enable_socket
@pytestmark_chromium
def test_integration_capture_returns_populated_result():
    """Real capture against the static fixture returns a PageCapture with PNG bytes + visible elements."""
    result = capture_page(_FIXTURE_URL)

    assert isinstance(result, PageCapture)
    assert result.image_bytes.startswith(b"\x89PNG"), "screenshot is not a PNG"
    tags = [e.tag for e in result.dom_elements]
    # Must include the four visible elements (image, h1, input, button "Sign up",
    # and the wide button — five visible elements in total).
    assert "button" in tags
    assert "h1" in tags
    assert "img" in tags
    assert "input" in tags
    # Must NOT include the hidden/faded/off-screen elements.
    texts = [e.text for e in result.dom_elements]
    assert "Hidden" not in texts
    assert "Fading" not in texts
    assert "Footer link" not in texts


@pytest.mark.enable_socket
@pytestmark_chromium
def test_integration_signup_bbox_sensible():
    """The Sign up button has a bbox inside the viewport with positive dimensions."""
    result = capture_page(_FIXTURE_URL)
    signup = next(
        (e for e in result.dom_elements if e.tag == "button" and e.text == "Sign up"),
        None,
    )
    assert signup is not None, "Sign up button missing from DOM payload"
    assert 0 <= signup.x <= 1280
    assert 0 <= signup.y <= 800
    assert signup.w > 0 and signup.h > 0
    # The fixture positions the Sign up button at approximately x=16, y=~212, w=120, h=40.
    # Allow a ±3 px band for layout variance.
    assert abs(signup.x - 16) <= 3
    assert abs(signup.w - 120) <= 3


@pytest.mark.enable_socket
@pytestmark_chromium
def test_integration_wide_button_clamping():
    """The 2000px-wide button has x clamped to 0 and w unclamped at 2000."""
    result = capture_page(_FIXTURE_URL)
    wide = next(
        (e for e in result.dom_elements if e.tag == "button" and e.text == "Wide"),
        None,
    )
    assert wide is not None, "Wide button missing from DOM payload"
    assert wide.x == 0
    assert wide.w >= 1280, f"expected w >= 1280 (unclamped), got {wide.w}"


@pytest.mark.enable_socket
@pytestmark_chromium
def test_integration_axe_runs_on_same_page():
    """axe.run completes and produces an AxeCoreResult (may be empty)."""
    result = capture_page(_FIXTURE_URL)
    assert isinstance(result.axe_result, AxeCoreResult)


# ---------------------------------------------------------------------------
# Handler-routing unit test (covered by this module to keep the new surface together)
# ---------------------------------------------------------------------------

def test_handler_url_branch_calls_capture_page_not_run_axe_or_extract_dom(mocker):
    """analyze_ui_screenshot(url) → capture_page is called; legacy run_axe/extract_dom are NOT."""
    from ui_analyzer.handler import analyze_ui_screenshot
    from unittest.mock import MagicMock

    mock_capture = mocker.patch(
        "ui_analyzer.handler.capture_page",
        return_value=PageCapture(
            image_bytes=_FAKE_PNG_BYTES,
            image_width_px=1280,
            image_height_px=800,
            dom_elements=[],
            axe_result=AxeCoreResult(findings=[]),
        ),
    )
    mock_run_axe = mocker.patch("ui_analyzer.handler.run_axe")
    mock_extract_dom = mocker.patch("ui_analyzer.handler.extract_dom")
    mocker.patch("ui_analyzer.handler.write_run")

    mock_client = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=(
        "<audit_report>"
        "<confidence level=\"medium\">ok</confidence>"
        "<inventory>x</inventory>"
        "<structure_observation>x</structure_observation>"
        "<tier1_findings></tier1_findings>"
        "<tier2_findings></tier2_findings>"
        "<tier3_findings></tier3_findings>"
        "<tier4_findings></tier4_findings>"
        "</audit_report>"
    ))]
    mock_resp.stop_reason = "end_turn"
    mock_resp.usage = MagicMock(
        input_tokens=1, output_tokens=1,
        cache_creation_input_tokens=0, cache_read_input_tokens=0,
    )
    mock_client.return_value.messages.create.return_value = mock_resp

    analyze_ui_screenshot("https://example.com", "web_dashboard", verify=False)

    mock_capture.assert_called_once_with("https://example.com")
    mock_run_axe.assert_not_called()
    mock_extract_dom.assert_not_called()


def test_handler_image_url_branch_does_not_call_capture_page(mocker):
    """Image-URL input (.png) → capture_page is NOT called; resolve() handles it."""
    from ui_analyzer.handler import analyze_ui_screenshot
    from ui_analyzer.image_source import ResolvedImage
    from unittest.mock import MagicMock

    mock_capture = mocker.patch("ui_analyzer.handler.capture_page")
    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=ResolvedImage(
            bytes=_FAKE_PNG_BYTES, source_type="url",
            width_px=1280, height_px=800,
        ),
    )
    mocker.patch("ui_analyzer.handler.write_run")

    mock_client = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=(
        "<audit_report>"
        "<confidence level=\"medium\">ok</confidence>"
        "<inventory>x</inventory>"
        "<structure_observation>x</structure_observation>"
        "<tier1_findings></tier1_findings>"
        "<tier2_findings></tier2_findings>"
        "<tier3_findings></tier3_findings>"
        "<tier4_findings></tier4_findings>"
        "</audit_report>"
    ))]
    mock_resp.stop_reason = "end_turn"
    mock_resp.usage = MagicMock(
        input_tokens=1, output_tokens=1,
        cache_creation_input_tokens=0, cache_read_input_tokens=0,
    )
    mock_client.return_value.messages.create.return_value = mock_resp

    analyze_ui_screenshot("https://example.com/shot.png", "web_dashboard", verify=False)

    mock_capture.assert_not_called()
