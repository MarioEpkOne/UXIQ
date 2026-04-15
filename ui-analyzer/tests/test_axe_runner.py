"""Tests for ui_analyzer.axe_runner — run_axe() never raises."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from ui_analyzer.axe_runner import AxeCoreResult, AxeFailure, run_axe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pw_context(
    *,
    inject_raises: Exception | None = None,
    evaluate_raises: Exception | None = None,
    outer_raises: Exception | None = None,
    axe_raw: dict | None = None,
):
    """Build a nested mock replacing sync_playwright()."""
    mock_page = MagicMock()
    mock_page.goto.return_value = MagicMock()

    if inject_raises is not None:
        mock_page.add_script_tag.side_effect = inject_raises
    else:
        mock_page.add_script_tag.return_value = None

    if evaluate_raises is not None:
        mock_page.evaluate.side_effect = evaluate_raises
    else:
        mock_page.evaluate.return_value = axe_raw or {"violations": [], "passes": []}

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw_instance = MagicMock()
    mock_pw_instance.chromium.launch.return_value = mock_browser

    mock_pw_cm = MagicMock()
    mock_pw_cm.__enter__ = MagicMock(return_value=mock_pw_instance)
    mock_pw_cm.__exit__ = MagicMock(return_value=False)

    if outer_raises is not None:
        mock_pw_cm.__enter__.side_effect = outer_raises

    return mock_pw_cm


# ---------------------------------------------------------------------------
# test_run_axe_returns_none_on_injection_failure
# ---------------------------------------------------------------------------

def test_run_axe_returns_axe_failure_on_injection_failure(mocker):
    """add_script_tag raising Exception → AxeFailure returned, no exception propagated."""
    mock_cm = _make_pw_context(inject_raises=Exception("CDN unreachable"))
    mocker.patch("ui_analyzer.axe_runner.sync_playwright", return_value=mock_cm)

    result = run_axe("https://example.com")

    assert isinstance(result, AxeFailure)
    assert "injection" in result.reason.lower() or "js" in result.reason.lower()


# ---------------------------------------------------------------------------
# test_run_axe_returns_none_on_evaluation_timeout
# ---------------------------------------------------------------------------

def test_run_axe_returns_axe_failure_on_evaluation_timeout(mocker):
    """page.evaluate raising TimeoutError → AxeFailure returned, no exception propagated."""
    mock_cm = _make_pw_context(evaluate_raises=TimeoutError("evaluation timed out"))
    mocker.patch("ui_analyzer.axe_runner.sync_playwright", return_value=mock_cm)

    result = run_axe("https://example.com")

    assert isinstance(result, AxeFailure)


# ---------------------------------------------------------------------------
# test_run_axe_returns_none_on_unexpected_error
# ---------------------------------------------------------------------------

def test_run_axe_returns_axe_failure_on_unexpected_error(mocker):
    """Outer sync_playwright context raising RuntimeError → AxeFailure returned."""
    mock_cm = _make_pw_context(outer_raises=RuntimeError("unexpected playwright error"))
    mocker.patch("ui_analyzer.axe_runner.sync_playwright", return_value=mock_cm)

    result = run_axe("https://example.com")

    assert isinstance(result, AxeFailure)


# ---------------------------------------------------------------------------
# test_run_axe_never_raises — parametrized over failure modes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("failure_mode", [
    "injection_failure",
    "evaluate_timeout",
    "evaluate_runtime_error",
    "outer_runtime_error",
])
def test_run_axe_never_raises(mocker, failure_mode):
    """Any exception inside run_axe() → returns AxeFailure, never raises."""
    if failure_mode == "injection_failure":
        mock_cm = _make_pw_context(inject_raises=Exception("oops"))
    elif failure_mode == "evaluate_timeout":
        mock_cm = _make_pw_context(evaluate_raises=TimeoutError("timed out"))
    elif failure_mode == "evaluate_runtime_error":
        mock_cm = _make_pw_context(evaluate_raises=RuntimeError("axe failed"))
    else:  # outer_runtime_error
        mock_cm = _make_pw_context(outer_raises=RuntimeError("playwright broken"))

    mocker.patch("ui_analyzer.axe_runner.sync_playwright", return_value=mock_cm)

    result = run_axe("https://example.com")
    assert isinstance(result, AxeFailure)


# ---------------------------------------------------------------------------
# test_run_axe_success — happy path returns AxeCoreResult
# ---------------------------------------------------------------------------

def test_run_axe_success_returns_axe_core_result(mocker):
    """Successful axe run with no violations → AxeCoreResult with empty findings."""
    mock_cm = _make_pw_context(axe_raw={"violations": [], "passes": []})
    mocker.patch("ui_analyzer.axe_runner.sync_playwright", return_value=mock_cm)

    result = run_axe("https://example.com")

    assert isinstance(result, AxeCoreResult)
    assert result.findings == []
