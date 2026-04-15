"""Tests for ui_analyzer.prompt_builder — build_thread() and SYSTEM_PROMPT."""
from __future__ import annotations

import pytest

from ui_analyzer.axe_runner import AxeCoreResult, AxeFailure
from ui_analyzer.context_events import ContextEvent
from ui_analyzer.prompt_builder import build_thread
from ui_analyzer.prompts import SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build(*, axe_result=None, source_type="file", app_type="web_dashboard"):
    return build_thread(
        app_type=app_type,
        source_type=source_type,
        image_source_value="test_source",
        viewport_width=1280,
        viewport_height=800,
        axe_result=axe_result,
    )


# ---------------------------------------------------------------------------
# test_build_thread_with_axe_data
# ---------------------------------------------------------------------------

def test_build_thread_with_axe_data():
    """AxeCoreResult present → event[1].type == 'axe_core_result', tier1_mode == 'authoritative'."""
    events = _build(axe_result=AxeCoreResult(findings=[]), source_type="url")

    types = [e.type for e in events]
    assert "axe_core_result" in types
    assert events[1].type == "axe_core_result"
    assert events[0].data["tier1_mode"] == "authoritative"


# ---------------------------------------------------------------------------
# test_build_thread_axe_failure_url_mode
# ---------------------------------------------------------------------------

def test_build_thread_axe_failure_url_mode():
    """AxeFailure present (URL mode) → event[1].type == 'axe_unavailable', reason propagated."""
    events = _build(
        axe_result=AxeFailure(reason="axe-core timed out"),
        source_type="url",
    )

    assert events[1].type == "axe_unavailable"
    assert events[1].data["reason"] == "axe-core timed out"
    assert events[0].data["tier1_mode"] == "estimated"


# ---------------------------------------------------------------------------
# test_build_thread_file_mode
# ---------------------------------------------------------------------------

def test_build_thread_file_mode():
    """source_type='file', axe_result=None → no axe event, event[1].type == 'rubric_tier1'."""
    events = _build(axe_result=None, source_type="file")

    types = [e.type for e in events]
    assert "axe_core_result" not in types
    assert "axe_unavailable" not in types
    assert events[1].type == "rubric_tier1"


# ---------------------------------------------------------------------------
# test_build_thread_canonical_order
# ---------------------------------------------------------------------------

def test_build_thread_canonical_order():
    """With axe_result present, event order: analysis_request → axe_core_result → rubric_tier1
    → rubric_tier2 → rubric_tier3 → rubric_tier4 → output_schema."""
    events = _build(axe_result=AxeCoreResult(findings=[]), source_type="url")

    types = [e.type for e in events]
    expected = [
        "analysis_request",
        "axe_core_result",
        "rubric_tier1",
        "rubric_tier2",
        "rubric_tier3",
        "rubric_tier4",
        "output_schema",
    ]
    assert types == expected


# ---------------------------------------------------------------------------
# test_analysis_request_contains_viewport
# ---------------------------------------------------------------------------

def test_analysis_request_contains_viewport():
    """events[0] (analysis_request) contains viewport_width=1280 and viewport_height=800."""
    events = _build()

    req = events[0]
    assert req.type == "analysis_request"
    assert req.data["viewport_width"] == 1280
    assert req.data["viewport_height"] == 800


# ---------------------------------------------------------------------------
# test_system_prompt_structure
# ---------------------------------------------------------------------------

def test_system_prompt_structure():
    """SYSTEM_PROMPT contains required keywords."""
    assert "inventory" in SYSTEM_PROMPT
    assert "structure" in SYSTEM_PROMPT
    assert "rubric" in SYSTEM_PROMPT
    assert "Do not compute numeric scores" in SYSTEM_PROMPT
