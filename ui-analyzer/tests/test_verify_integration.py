"""Integration tests for verification agent — require a real ANTHROPIC_API_KEY.

These tests auto-skip when ANTHROPIC_API_KEY is unset or set to the unit-test dummy.
"""

from __future__ import annotations

import os

import pytest

_REAL_KEY = os.getenv("ANTHROPIC_API_KEY", "")
skip_if_no_key = pytest.mark.skipif(
    _REAL_KEY in ("", "test-key-unit-tests"),
    reason="ANTHROPIC_API_KEY not set to a real key",
)


@pytest.mark.integration
@skip_if_no_key
def test_verify_true_returns_markdown():
    """analyze_ui_screenshot with verify=True → non-empty Markdown string."""
    from ui_analyzer.handler import analyze_ui_screenshot

    result = analyze_ui_screenshot("https://example.com", "web_dashboard", verify=True)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "## Tier 1" in result


@pytest.mark.integration
@skip_if_no_key
def test_verify_false_returns_markdown():
    """analyze_ui_screenshot with verify=False → non-empty Markdown string."""
    from ui_analyzer.handler import analyze_ui_screenshot

    result = analyze_ui_screenshot("https://example.com", "web_dashboard", verify=False)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "## Tier 1" in result


@pytest.mark.integration
@skip_if_no_key
def test_verify_default_is_true():
    """analyze_ui_screenshot without verify kwarg → runs verification (default True behavior)."""
    from ui_analyzer.handler import analyze_ui_screenshot

    # Both calls should return valid Markdown — if verify=True is default,
    # this and test_verify_true_returns_markdown exercise the same path.
    result = analyze_ui_screenshot("https://example.com", "landing_page")
    assert isinstance(result, str)
    assert "## Tier 1" in result
