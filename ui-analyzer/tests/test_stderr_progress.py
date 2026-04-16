"""Tests for StderrProgress in cli.py.

All tests mock sys.stderr to capture output; no real stderr output is produced.
"""
from __future__ import annotations

import io
import time
from contextlib import redirect_stderr
from unittest.mock import patch

import pytest

from ui_analyzer.cli import StderrProgress


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture(fn) -> str:
    """Run fn(), capture and return stderr output as a string."""
    buf = io.StringIO()
    with redirect_stderr(buf):
        fn()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_stage_start_writes_arrow_label_to_stderr():
    """stage_start → line starting with '→' and the label."""
    p = StderrProgress()
    output = _capture(lambda: p.stage_start("image", "Loading image..."))
    assert "→" in output or "->" in output
    assert "Loading image..." in output


def test_stage_end_writes_checkmark_with_elapsed():
    """stage_end → line with '✓' (or 'OK'), label, and elapsed time in (Xs) format."""
    p = StderrProgress()
    output = _capture(lambda: p.stage_end("image", "Image loaded", 1.23))
    assert "✓" in output or "OK" in output
    assert "Image loaded" in output
    assert "1.2s" in output


def test_stage_end_with_detail_appends_detail():
    """stage_end with detail → detail string appears after em-dash."""
    p = StderrProgress()
    output = _capture(lambda: p.stage_end("axe", "Accessibility checks done", 0.5, "3 violation(s) found"))
    assert "3 violation(s) found" in output
    assert "Accessibility checks done" in output


def test_stage_end_without_detail_no_em_dash():
    """stage_end with empty detail → no em-dash or detail suffix."""
    p = StderrProgress()
    output = _capture(lambda: p.stage_end("axe", "Accessibility checks done", 0.5, ""))
    # em-dash (—) should not appear when detail is empty
    assert "\u2014" not in output
    assert "Accessibility checks done" in output


def test_done_writes_total_elapsed():
    """done() → line with '✓ Done (total: Xs)' on stderr."""
    p = StderrProgress()
    output = _capture(lambda: p.done())
    assert "Done" in output
    assert "total:" in output


def test_multiple_stages_sequential():
    """Multiple stage_start/stage_end calls produce sequential lines in order."""
    p = StderrProgress()
    buf = io.StringIO()
    with redirect_stderr(buf):
        p.stage_start("image", "Loading image...")
        p.stage_end("image", "Image loaded", 0.1)
        p.stage_start("claude", "Analysing with Claude...")
        p.stage_end("claude", "Analysis complete", 2.5)
        p.done()
    output = buf.getvalue()
    lines = [ln for ln in output.splitlines() if ln.strip()]
    assert len(lines) == 5
    assert "Loading image..." in lines[0]
    assert "Image loaded" in lines[1]
    assert "Analysing with Claude..." in lines[2]
    assert "Analysis complete" in lines[3]
    assert "Done" in lines[4]
