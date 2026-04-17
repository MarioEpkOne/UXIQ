"""Tests for ui_analyzer.dom_extractor — extract_dom() and DomElement/DomElements/DomFailure."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ui_analyzer.dom_extractor import (
    DomElement,
    DomElements,
    DomFailure,
    extract_dom,
)

_SAMPLE_RAW = [
    {
        "tag": "button",
        "role": "",
        "text": "Sign in",
        "aria_label": "",
        "placeholder": "",
        "input_type": "",
    },
    {
        "tag": "a",
        "role": "",
        "text": "Pricing",
        "aria_label": "",
        "placeholder": "",
        "input_type": "",
    },
    {
        "tag": "input",
        "role": "",
        "text": "",
        "aria_label": "Email address",
        "placeholder": "you@example.com",
        "input_type": "email",
    },
]


# ---------------------------------------------------------------------------
# test_extract_dom_parses_elements_correctly
# ---------------------------------------------------------------------------

def test_extract_dom_parses_elements_correctly():
    """Mock Playwright evaluate → DomElements with correctly mapped DomElement objects."""
    mock_page = MagicMock()
    mock_page.goto.return_value = None
    mock_page.evaluate.return_value = _SAMPLE_RAW

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser
    mock_pw.__enter__ = MagicMock(return_value=mock_pw)
    mock_pw.__exit__ = MagicMock(return_value=False)

    with patch("ui_analyzer.dom_extractor.sync_playwright", return_value=mock_pw):
        result = extract_dom("https://example.com")

    assert isinstance(result, DomElements)
    assert len(result.elements) == 3

    btn = result.elements[0]
    assert btn.tag == "button"
    assert btn.text == "Sign in"
    assert btn.aria_label == ""

    # New fields default when raw dict lacks them (legacy JS selector doesn't emit them)
    assert btn.alt == ""
    assert (btn.x, btn.y, btn.w, btn.h) == (0, 0, 0, 0)

    inp = result.elements[2]
    assert inp.tag == "input"
    assert inp.aria_label == "Email address"
    assert inp.placeholder == "you@example.com"
    assert inp.input_type == "email"


def test_dom_element_new_style_fields_default_when_unspecified():
    """DomElement constructed without style args has font_size_px=0.0, *_contrast_ratio=None, etc."""
    el = DomElement(
        tag="button", role="", text="", aria_label="",
        placeholder="", input_type="",
    )
    assert el.font_size_px == 0.0
    assert el.font_weight == 400
    assert el.color == ""
    assert el.effective_bg_color == ""
    assert el.border_color == ""
    assert el.border_width_px == 0.0
    assert el.text_contrast_ratio is None
    assert el.ui_contrast_ratio is None


# ---------------------------------------------------------------------------
# test_extract_dom_returns_failure_on_playwright_timeout
# ---------------------------------------------------------------------------

def test_extract_dom_returns_failure_on_playwright_timeout():
    """PlaywrightTimeout during page.goto → DomFailure returned, no exception raised."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    mock_page = MagicMock()
    mock_page.goto.side_effect = PlaywrightTimeout("timed out")

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser
    mock_pw.__enter__ = MagicMock(return_value=mock_pw)
    mock_pw.__exit__ = MagicMock(return_value=False)

    with patch("ui_analyzer.dom_extractor.sync_playwright", return_value=mock_pw):
        result = extract_dom("https://slow.example.com")

    assert isinstance(result, DomFailure)
    assert "30s" in result.reason


# ---------------------------------------------------------------------------
# test_extract_dom_returns_failure_on_js_error
# ---------------------------------------------------------------------------

def test_extract_dom_returns_failure_on_js_error():
    """JS evaluate raises → DomFailure returned, no exception raised."""
    mock_page = MagicMock()
    mock_page.goto.return_value = None
    mock_page.evaluate.side_effect = RuntimeError("JS execution context was destroyed")

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser
    mock_pw.__enter__ = MagicMock(return_value=mock_pw)
    mock_pw.__exit__ = MagicMock(return_value=False)

    with patch("ui_analyzer.dom_extractor.sync_playwright", return_value=mock_pw):
        result = extract_dom("https://example.com")

    assert isinstance(result, DomFailure)
    assert "JS evaluation failed" in result.reason


# ---------------------------------------------------------------------------
# test_extract_dom_empty_result
# ---------------------------------------------------------------------------

def test_extract_dom_empty_result():
    """Evaluate returns empty list → DomElements(elements=[]) returned, not DomFailure."""
    mock_page = MagicMock()
    mock_page.goto.return_value = None
    mock_page.evaluate.return_value = []

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser
    mock_pw.__enter__ = MagicMock(return_value=mock_pw)
    mock_pw.__exit__ = MagicMock(return_value=False)

    with patch("ui_analyzer.dom_extractor.sync_playwright", return_value=mock_pw):
        result = extract_dom("https://example.com")

    assert isinstance(result, DomElements)
    assert result.elements == []
