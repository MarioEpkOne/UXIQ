"""Tests for ui_analyzer.run_writer — write_run(), _source_slug(), _iso_timestamp()."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ui_analyzer.run_writer import _source_slug, write_run
from ui_analyzer.xml_parser import AuditReport


# ---------------------------------------------------------------------------
# _source_slug unit tests
# ---------------------------------------------------------------------------

def test_slug_plain_hostname():
    """Plain hostname with no path → slug is hostname with dots replaced."""
    assert _source_slug("https://example.com") == "example-com"


def test_slug_hostname_and_path():
    """Hostname + path → slug is hostname + first path segment."""
    assert _source_slug("https://example.com/dashboard/v2") == "example-com-dashboard"


def test_slug_with_query_string():
    """Query string stripped before slug derivation."""
    result = _source_slug("https://foo.com/path?q=search&lang=en")
    assert result == "foo-com-path"


def test_slug_with_special_characters():
    """Special characters in hostname/path replaced with hyphens."""
    result = _source_slug("https://foo.bar.com/my_page")
    assert result == "foo-bar-com-my-page"


def test_slug_truncated_at_40():
    """Slug truncated to 40 characters."""
    long_url = "https://averylonghostname.example.co.uk/averylongpathsegmenthere"
    result = _source_slug(long_url)
    assert len(result) <= 40


# ---------------------------------------------------------------------------
# write_run — debug file content tests
# ---------------------------------------------------------------------------

def test_write_run_creates_file_with_correct_sections(tmp_path):
    """write_run creates a Markdown file with all required sections."""
    report = AuditReport(
        confidence_level="high",
        confidence_reason="Clear screenshot.",
        inventory="Two buttons, one heading.",
        structure_observation="Left-aligned layout.",
    )
    rendered = "# UI Analysis Report\n\n(rendered output)"

    with patch("ui_analyzer.run_writer._RUNS_DIR", tmp_path):
        write_run(
            url="https://example.com",
            app_type="landing_page",
            model="claude-sonnet-4-6",
            report=report,
            rendered_output=rendered,
        )

    files = list(tmp_path.glob("*.md"))
    assert len(files) == 1

    content = files[0].read_text(encoding="utf-8")
    assert "## What Claude Sees" in content
    assert "## Full Analysis" in content
    assert "**Level:** high" in content
    assert "**Reason:** Clear screenshot." in content
    assert "Two buttons, one heading." in content
    assert "Left-aligned layout." in content
    assert rendered in content
    assert "**URL:** https://example.com" in content
    assert "**App type:** landing_page" in content
    assert "**Model:** claude-sonnet-4-6" in content


def test_write_run_empty_fields_render_placeholders(tmp_path):
    """Empty confidence/inventory/structure → placeholder strings in file."""
    report = AuditReport(
        confidence_level="",
        confidence_reason="",
        inventory="",
        structure_observation="",
    )

    with patch("ui_analyzer.run_writer._RUNS_DIR", tmp_path):
        write_run(
            url="https://example.com",
            app_type="web_dashboard",
            model="claude-sonnet-4-6",
            report=report,
            rendered_output="",
        )

    content = list(tmp_path.glob("*.md"))[0].read_text(encoding="utf-8")
    assert "**Level:** —" in content
    assert "**Reason:** —" in content
    assert "*Claude produced no inventory.*" in content
    assert "*Claude produced no structure observation.*" in content


def test_write_run_soft_failure_on_permission_error(tmp_path):
    """PermissionError on open → write_run returns normally without raising."""
    report = AuditReport()

    with patch("ui_analyzer.run_writer._RUNS_DIR", tmp_path):
        with patch("pathlib.Path.write_text", side_effect=PermissionError("no write")):
            # Must not raise
            write_run(
                url="https://example.com",
                app_type="web_dashboard",
                model="claude-sonnet-4-6",
                report=report,
                rendered_output="output",
            )


def test_write_run_creates_runs_dir_if_missing(tmp_path):
    """runs/ directory created automatically if it does not exist."""
    runs_dir = tmp_path / "runs"
    assert not runs_dir.exists()

    with patch("ui_analyzer.run_writer._RUNS_DIR", runs_dir):
        write_run(
            url="https://example.com",
            app_type="web_dashboard",
            model="claude-sonnet-4-6",
            report=AuditReport(),
            rendered_output="output",
        )

    assert runs_dir.exists()
    assert len(list(runs_dir.glob("*.md"))) == 1
