"""Integration tests for verification agent — require a real ANTHROPIC_API_KEY.

These tests auto-skip when ANTHROPIC_API_KEY is unset or set to the unit-test dummy.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import anthropic
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


@pytest.mark.integration
@skip_if_no_key
def test_cache_tokens_written_on_primary_read_on_verifier(monkeypatch):
    """Primary call writes cache tokens; verifier call reads them.

    Patches the Anthropic client constructor in ui_analyzer.handler to wrap
    messages.create with a spy, capturing each response's usage object.
    Asserts cache_creation_input_tokens > 0 on the primary call (cache was
    written) and cache_read_input_tokens > 0 on the verifier call (cache was
    hit).
    """
    import ui_analyzer.handler as handler_module

    captured_responses: list[anthropic.types.Message] = []

    real_anthropic_cls = anthropic.Anthropic

    class SpyingAnthropicClient:
        """Wraps a real Anthropic client and records every messages.create response."""

        def __init__(self, **kwargs):
            self._real = real_anthropic_cls(**kwargs)
            self.messages = _SpyingMessages(self._real.messages, captured_responses)

    class _SpyingMessages:
        def __init__(self, real_messages, log: list):
            self._real = real_messages
            self._log = log

        def create(self, **kwargs):
            response = self._real.create(**kwargs)
            self._log.append(response)
            return response

    monkeypatch.setattr(handler_module, "anthropic", type(
        "_PatchedAnthropic",
        (),
        {
            "Anthropic": SpyingAnthropicClient,
            "APITimeoutError": anthropic.APITimeoutError,
            "RateLimitError": anthropic.RateLimitError,
        },
    )())
    monkeypatch.setenv("UXIQ_ANTHROPIC_API_KEY", _REAL_KEY)

    from ui_analyzer.handler import analyze_ui_screenshot

    analyze_ui_screenshot("https://example.com", "web_dashboard", verify=True)

    assert len(captured_responses) >= 2, (
        f"Expected at least 2 API responses (primary + verifier), got {len(captured_responses)}"
    )

    primary_usage = captured_responses[0].usage
    verifier_usage = captured_responses[1].usage

    assert primary_usage.cache_creation_input_tokens > 0, (
        f"Primary call should have written cache tokens, got "
        f"cache_creation_input_tokens={primary_usage.cache_creation_input_tokens}"
    )
    assert verifier_usage.cache_read_input_tokens > 0, (
        f"Verifier call should have read cache tokens, got "
        f"cache_read_input_tokens={verifier_usage.cache_read_input_tokens}"
    )
