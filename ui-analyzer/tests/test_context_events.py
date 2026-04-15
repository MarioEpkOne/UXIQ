"""Tests for ui_analyzer.context_events — event_to_xml() and thread_to_prompt()."""
from __future__ import annotations

import pytest

from ui_analyzer.axe_runner import AxeCoreResult
from ui_analyzer.context_events import ContextEvent, event_to_xml, thread_to_prompt


# ---------------------------------------------------------------------------
# test_event_to_xml_with_dict
# ---------------------------------------------------------------------------

def test_event_to_xml_with_dict():
    """ContextEvent with dict data → YAML-serialized body inside XML tags."""
    event = ContextEvent(type="rubric_tier1", data={"protocol": "WCAG"})
    result = event_to_xml(event)

    assert result.startswith("<rubric_tier1>")
    assert result.endswith("</rubric_tier1>")
    assert "protocol: WCAG" in result


# ---------------------------------------------------------------------------
# test_event_to_xml_with_str
# ---------------------------------------------------------------------------

def test_event_to_xml_with_str():
    """ContextEvent with str data → verbatim body (no YAML) inside XML tags."""
    raw = "<some_raw_xml/>"
    event = ContextEvent(type="output_schema", data=raw)
    result = event_to_xml(event)

    assert result == f"<output_schema>\n{raw}\n</output_schema>"


# ---------------------------------------------------------------------------
# test_event_to_xml_with_dataclass
# ---------------------------------------------------------------------------

def test_event_to_xml_with_dataclass():
    """ContextEvent with dataclass data → serialized to YAML, no exception."""
    axe = AxeCoreResult(findings=[])
    event = ContextEvent(type="axe_core_result", data=axe)
    result = event_to_xml(event)

    assert "<axe_core_result>" in result
    assert "</axe_core_result>" in result
    # No exception raised; YAML body present
    assert len(result) > len("<axe_core_result></axe_core_result>")


# ---------------------------------------------------------------------------
# test_thread_to_prompt_structure
# ---------------------------------------------------------------------------

def test_thread_to_prompt_structure():
    """thread_to_prompt() wraps events with the correct preamble and closing question."""
    events = [ContextEvent(type="rubric_tier1", data={})]
    result = thread_to_prompt(events)

    assert result.startswith("Here is everything known about this analysis task:")
    assert result.endswith("What is the complete audit report?")


# ---------------------------------------------------------------------------
# test_thread_to_prompt_ordering
# ---------------------------------------------------------------------------

def test_thread_to_prompt_ordering():
    """Multiple events → output order matches input list order."""
    events = [
        ContextEvent(type="analysis_request", data={"app_type": "forms"}),
        ContextEvent(type="rubric_tier1", data={"protocol": "WCAG"}),
        ContextEvent(type="output_schema", data="<schema/>"),
    ]
    result = thread_to_prompt(events)

    pos_request = result.index("<analysis_request>")
    pos_tier1 = result.index("<rubric_tier1>")
    pos_schema = result.index("<output_schema>")

    assert pos_request < pos_tier1 < pos_schema
