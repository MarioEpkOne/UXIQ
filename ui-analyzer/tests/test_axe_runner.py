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


# ---------------------------------------------------------------------------
# Tests for inapplicable-as-PASS (Fix Group 4C)
# ---------------------------------------------------------------------------

def test_parse_axe_result_inapplicable_added_to_passing_rules():
    """inapplicable rule in _RULE_TO_CRITERION → appears as PASS in findings."""
    from ui_analyzer.axe_runner import _parse_axe_result

    raw = {
        "violations": [],
        "passes": [],
        "inapplicable": [{"id": "color-contrast"}],
    }
    result = _parse_axe_result(raw)
    criterion_results = {f.criterion: f.result for f in result.findings}
    assert criterion_results.get("1.4.3") == "PASS"


def test_parse_axe_result_inapplicable_unknown_rule_ignored():
    """inapplicable rule not in _RULE_TO_CRITERION → silently ignored."""
    from ui_analyzer.axe_runner import _parse_axe_result

    raw = {
        "violations": [],
        "passes": [],
        "inapplicable": [{"id": "aria-required-attr"}],  # not in _RULE_TO_CRITERION
    }
    result = _parse_axe_result(raw)
    # No findings from unknown rules
    assert result.findings == []


# ---------------------------------------------------------------------------
# Tests for wcag22aa tag (Fix Group 4A)
# ---------------------------------------------------------------------------

def test_run_axe_js_contains_wcag22aa_tag(mocker):
    """The JS string passed to page.evaluate contains 'wcag22aa'."""
    mock_cm = _make_pw_context(axe_raw={"violations": [], "passes": []})
    mocker.patch("ui_analyzer.axe_runner.sync_playwright", return_value=mock_cm)

    run_axe("https://example.com")

    # Capture the JS string passed to page.evaluate
    mock_page = mock_cm.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value
    js_arg = mock_page.evaluate.call_args[0][0]
    assert "wcag22aa" in js_arg


# ---------------------------------------------------------------------------
# Tests for link-in-text-block mapping (authoritative-tier1-data spec)
# ---------------------------------------------------------------------------

def test_link_in_text_block_in_rule_to_criterion_maps_to_1_4_1():
    """link-in-text-block entry in _RULE_TO_CRITERION maps to criterion '1.4.1'."""
    from ui_analyzer.axe_runner import _RULE_TO_CRITERION
    assert _RULE_TO_CRITERION.get("link-in-text-block") == "1.4.1"


def test_rule_to_criterion_does_not_contain_removed_fake_ids():
    """Removed rule IDs that never matched axe output must be absent from the map."""
    from ui_analyzer.axe_runner import _RULE_TO_CRITERION
    assert "non-text-contrast" not in _RULE_TO_CRITERION
    assert "color-not-used-as-sole-meaning" not in _RULE_TO_CRITERION
    assert "focus-visible" not in _RULE_TO_CRITERION


def test_parse_axe_result_link_in_text_block_inapplicable_gives_pass():
    """link-in-text-block in inapplicable → PASS finding for criterion 1.4.1."""
    from ui_analyzer.axe_runner import _parse_axe_result

    raw = {
        "violations": [],
        "passes": [],
        "inapplicable": [{"id": "link-in-text-block"}],
    }
    result = _parse_axe_result(raw)
    criterion_results = {f.criterion: f.result for f in result.findings}
    assert criterion_results.get("1.4.1") == "PASS"


def test_parse_axe_result_link_in_text_block_violation_gives_fail():
    """link-in-text-block in violations → FAIL finding for criterion 1.4.1."""
    from ui_analyzer.axe_runner import _parse_axe_result

    raw = {
        "violations": [
            {
                "id": "link-in-text-block",
                "description": "Links must be distinguishable without relying on colour",
                "nodes": [{"target": ["a.read-more"], "any": []}],
            }
        ],
        "passes": [],
        "inapplicable": [],
    }
    result = _parse_axe_result(raw)
    criterion_results = {f.criterion: f.result for f in result.findings}
    assert criterion_results.get("1.4.1") == "FAIL"


def test_parse_axe_result_link_in_text_block_passes_gives_pass():
    """link-in-text-block in passes → PASS finding for criterion 1.4.1."""
    from ui_analyzer.axe_runner import _parse_axe_result

    raw = {
        "violations": [],
        "passes": [{"id": "link-in-text-block"}],
        "inapplicable": [],
    }
    result = _parse_axe_result(raw)
    criterion_results = {f.criterion: f.result for f in result.findings}
    assert criterion_results.get("1.4.1") == "PASS"


# ---------------------------------------------------------------------------
# Tests for vendor file (Fix Group 2)
# ---------------------------------------------------------------------------

def test_vendor_axe_min_js_exists_and_is_non_empty():
    """ui_analyzer/vendor/axe.min.js exists and has content."""
    import pathlib
    vendor_path = pathlib.Path(__file__).parent.parent / "ui_analyzer" / "vendor" / "axe.min.js"
    assert vendor_path.exists(), f"vendor file missing at {vendor_path}"
    assert vendor_path.stat().st_size > 0, "vendor file is empty"


def test_module_level_axe_js_is_non_empty_string():
    """Module-level _AXE_JS constant is a non-empty string."""
    from ui_analyzer.axe_runner import _AXE_JS
    assert isinstance(_AXE_JS, str)
    assert len(_AXE_JS) > 0
