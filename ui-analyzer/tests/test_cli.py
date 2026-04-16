"""Tests for cli.py — uxiq command-line interface.

All tests invoke via subprocess to avoid in-process SystemExit complications.
No ANTHROPIC_API_KEY is required for any test in this file.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

# Path to run: python3 -m ui_analyzer.cli
CLI_MODULE = [sys.executable, "-m", "ui_analyzer.cli"]


def _run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run the CLI with the given args. Inherits env unless overridden."""
    base_env = os.environ.copy()
    if env is not None:
        base_env.update(env)
    return subprocess.run(
        CLI_MODULE + list(args),
        capture_output=True,
        text=True,
        env=base_env,
    )


# ---------------------------------------------------------------------------
# uxiq --version
# ---------------------------------------------------------------------------

def test_version_exits_0_and_prints_version():
    """uxiq --version → exit 0, stdout contains 'uxiq '."""
    result = _run("--version")
    assert result.returncode == 0
    assert result.stdout.startswith("uxiq ")


# ---------------------------------------------------------------------------
# uxiq list-app-types
# ---------------------------------------------------------------------------

def test_list_app_types_prints_four_types():
    """uxiq list-app-types → exit 0, stdout has exactly 4 non-empty lines."""
    result = _run("list-app-types")
    assert result.returncode == 0
    lines = [ln for ln in result.stdout.strip().splitlines() if ln]
    assert len(lines) == 4
    assert "forms" in lines
    assert "landing_page" in lines
    assert "onboarding_flow" in lines
    assert "web_dashboard" in lines


# ---------------------------------------------------------------------------
# uxiq analyze — missing --app-type (argparse error)
# ---------------------------------------------------------------------------

def test_analyze_missing_app_type_exits_2():
    """uxiq analyze file.png (no --app-type) → exit 2, stderr mentions --app-type."""
    result = _run("analyze", "file.png")
    assert result.returncode == 2
    assert "--app-type" in result.stderr or "app-type" in result.stderr


# ---------------------------------------------------------------------------
# uxiq analyze — invalid --app-type (argparse choices error)
# ---------------------------------------------------------------------------

def test_analyze_invalid_app_type_exits_1_mentions_valid():
    """uxiq analyze file.png --app-type badvalue → exit 1, stderr has custom 'Invalid app-type' message."""
    result = _run("analyze", "file.png", "--app-type", "badvalue")
    assert result.returncode == 1
    assert "Invalid app-type" in result.stderr
    assert "Valid:" in result.stderr


# ---------------------------------------------------------------------------
# uxiq analyze — UIAnalyzerError (mocked)
# ---------------------------------------------------------------------------

def test_analyze_ui_analyzer_error_exits_1_to_stderr(mocker):
    """uxiq analyze with UIAnalyzerError → exit 1, error message on stderr."""
    from ui_analyzer.exceptions import UIAnalyzerError
    from ui_analyzer import cli

    with patch("ui_analyzer.handler.analyze_ui_screenshot",
               side_effect=UIAnalyzerError("test error from mock")):
        import argparse
        args = argparse.Namespace(
            image_source="fake.png",
            app_type="web_dashboard",
            output=None,
            quiet=True,
            func=cli._cmd_analyze,
        )
        with pytest.raises(SystemExit) as exc_info:
            cli._cmd_analyze(args)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# uxiq analyze -o /tmp/out.md — success path (mocked)
# ---------------------------------------------------------------------------

def test_analyze_output_flag_writes_file(mocker):
    """uxiq analyze -o /tmp/out.md → file written, 'Report saved to' on stderr."""
    from ui_analyzer import cli

    FAKE_REPORT = "# UI Analysis Report\n\nFake content."

    with patch("ui_analyzer.handler.analyze_ui_screenshot", return_value=FAKE_REPORT):
        import argparse
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            args = argparse.Namespace(
                image_source="fake.png",
                app_type="web_dashboard",
                output=tmp_path,
                quiet=True,
                func=cli._cmd_analyze,
            )
            # Capture stderr
            import io
            from contextlib import redirect_stderr
            captured_stderr = io.StringIO()
            with redirect_stderr(captured_stderr):
                cli._cmd_analyze(args)

            with open(tmp_path, encoding="utf-8") as fh:
                content = fh.read()
            assert content == FAKE_REPORT
            assert "Report saved to" in captured_stderr.getvalue()
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# uxiq analyze -o /nonexistent/dir/out.md — OSError path
# ---------------------------------------------------------------------------

def test_analyze_output_bad_path_exits_1(mocker):
    """uxiq analyze -o /nonexistent/dir/out.md → exit 1, OSError message on stderr."""
    from ui_analyzer import cli

    FAKE_REPORT = "# UI Analysis Report\n\nFake content."

    with patch("ui_analyzer.handler.analyze_ui_screenshot", return_value=FAKE_REPORT):
        import argparse
        args = argparse.Namespace(
            image_source="fake.png",
            app_type="web_dashboard",
            output="/nonexistent/directory/out.md",
            quiet=True,
            func=cli._cmd_analyze,
        )
        with pytest.raises(SystemExit) as exc_info:
            cli._cmd_analyze(args)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# uxiq (no subcommand) → help + exit 0
# ---------------------------------------------------------------------------

def test_no_subcommand_exits_0_and_prints_help():
    """uxiq (no subcommand) → exit 0, stdout contains 'usage'."""
    result = _run()
    assert result.returncode == 0
    assert "usage" in result.stdout.lower() or "uxiq" in result.stdout.lower()


# ---------------------------------------------------------------------------
# ANTHROPIC_API_KEY not set → list-app-types still works
# ---------------------------------------------------------------------------

def test_list_app_types_works_without_api_key():
    """uxiq list-app-types with no UXIQ_ANTHROPIC_API_KEY → exit 0 (env check is in handler)."""
    env = os.environ.copy()
    env.pop("UXIQ_ANTHROPIC_API_KEY", None)
    result = subprocess.run(
        CLI_MODULE + ["list-app-types"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "forms" in result.stdout


# ---------------------------------------------------------------------------
# ANTHROPIC_API_KEY not set → --version still works
# ---------------------------------------------------------------------------

def test_version_works_without_api_key():
    """uxiq --version with no UXIQ_ANTHROPIC_API_KEY → exit 0."""
    env = os.environ.copy()
    env.pop("UXIQ_ANTHROPIC_API_KEY", None)
    result = subprocess.run(
        CLI_MODULE + ["--version"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert result.stdout.startswith("uxiq ")


# ---------------------------------------------------------------------------
# --quiet / -q flag tests
# ---------------------------------------------------------------------------

def test_quiet_flag_passes_none_progress(mocker):
    """--quiet → progress=None is passed to analyze_ui_screenshot."""
    from ui_analyzer import cli
    import argparse

    FAKE_REPORT = "# UI Analysis Report\n\nFake."

    with patch("ui_analyzer.handler.analyze_ui_screenshot", return_value=FAKE_REPORT) as mock_analyze:
        args = argparse.Namespace(
            image_source="https://example.com",
            app_type="web_dashboard",
            output=None,
            quiet=True,
            func=cli._cmd_analyze,
        )
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            cli._cmd_analyze(args)

        _, kwargs = mock_analyze.call_args
        assert kwargs.get("progress") is None


def test_quiet_suppresses_stderr_progress(mocker):
    """--quiet → no progress lines written to stderr during successful run."""
    from ui_analyzer import cli
    import argparse
    import io
    from contextlib import redirect_stderr

    FAKE_REPORT = "# UI Analysis Report\n\nFake."

    with patch("ui_analyzer.handler.analyze_ui_screenshot", return_value=FAKE_REPORT):
        args = argparse.Namespace(
            image_source="https://example.com",
            app_type="web_dashboard",
            output=None,
            quiet=True,
            func=cli._cmd_analyze,
        )
        captured = io.StringIO()
        with redirect_stderr(captured):
            with patch("sys.stdout", io.StringIO()):
                cli._cmd_analyze(args)

    assert captured.getvalue() == ""


def test_no_quiet_flag_creates_stderr_progress(mocker):
    """Without --quiet → progress is not None; 'Done' appears in stderr output."""
    from ui_analyzer import cli
    import argparse
    import io
    from contextlib import redirect_stderr

    FAKE_REPORT = "# UI Analysis Report\n\nFake."

    with patch("ui_analyzer.handler.analyze_ui_screenshot", return_value=FAKE_REPORT):
        args = argparse.Namespace(
            image_source="https://example.com",
            app_type="web_dashboard",
            output=None,
            quiet=False,
            func=cli._cmd_analyze,
        )
        captured = io.StringIO()
        with redirect_stderr(captured):
            with patch("sys.stdout", io.StringIO()):
                cli._cmd_analyze(args)

    assert "Done" in captured.getvalue()


# ---------------------------------------------------------------------------
# uxiq model — show current model (default, no config)
# ---------------------------------------------------------------------------

def test_model_show_default(tmp_path):
    """uxiq model with no config → prints default model with '(sonnet, default)'."""
    env = os.environ.copy()
    # Point config to a nonexistent file so no stored config is found
    env["HOME"] = str(tmp_path)
    result = subprocess.run(
        CLI_MODULE + ["model"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0
    assert "claude-sonnet-4-6" in result.stdout
    assert "sonnet" in result.stdout
    assert "default" in result.stdout


# ---------------------------------------------------------------------------
# uxiq model set opus — writes config and prints confirmation
# ---------------------------------------------------------------------------

def test_model_set_opus(tmp_path):
    """uxiq model set opus → exit 0, prints 'Model set to: claude-opus-4-6 (opus)'."""
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    result = subprocess.run(
        CLI_MODULE + ["model", "set", "opus"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0
    assert "claude-opus-4-6" in result.stdout
    assert "opus" in result.stdout


# ---------------------------------------------------------------------------
# uxiq model set bad — unknown alias → exit 1 with error message
# ---------------------------------------------------------------------------

def test_model_set_bad_alias_exits_1(tmp_path):
    """uxiq model set bad → exit 1, stderr contains 'Unknown model'."""
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    result = subprocess.run(
        CLI_MODULE + ["model", "set", "bad"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 1
    assert "Unknown model" in result.stderr


# ---------------------------------------------------------------------------
# uxiq analyze --model opus passes correct model ID to handler
# ---------------------------------------------------------------------------

def test_analyze_model_flag_passes_full_model_id_to_handler(mocker):
    """--model opus → analyze_ui_screenshot called with model='claude-opus-4-6'."""
    from ui_analyzer import cli
    import argparse

    FAKE_REPORT = "# UI Analysis Report\n\nFake."

    with patch("ui_analyzer.handler.analyze_ui_screenshot", return_value=FAKE_REPORT) as mock_analyze:
        args = argparse.Namespace(
            image_source="https://example.com",
            app_type="web_dashboard",
            output=None,
            quiet=True,
            model="opus",
            func=cli._cmd_analyze,
        )
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            cli._cmd_analyze(args)

    _, kwargs = mock_analyze.call_args
    assert kwargs.get("model") == "claude-opus-4-6"


# ---------------------------------------------------------------------------
# uxiq analyze --model bad_alias → exit 1 with error message
# ---------------------------------------------------------------------------

def test_analyze_bad_model_alias_exits_1():
    """uxiq analyze ... --model bad_alias → exit 1, stderr has 'Unknown model'."""
    result = _run(
        "analyze", "https://example.com",
        "--app-type", "web_dashboard",
        "--model", "bad_alias",
    )
    assert result.returncode == 1
    assert "Unknown model" in result.stderr


# ---------------------------------------------------------------------------
# uxiq analyze (no --model) uses model from config
# ---------------------------------------------------------------------------

def test_analyze_no_model_flag_reads_from_config(mocker, tmp_path):
    """uxiq analyze with no --model → model=None is passed to handler (handler reads config)."""
    from ui_analyzer import cli
    import argparse

    FAKE_REPORT = "# UI Analysis Report\n\nFake."

    with patch("ui_analyzer.handler.analyze_ui_screenshot", return_value=FAKE_REPORT) as mock_analyze:
        args = argparse.Namespace(
            image_source="https://example.com",
            app_type="web_dashboard",
            output=None,
            quiet=True,
            model=None,
            func=cli._cmd_analyze,
        )
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            cli._cmd_analyze(args)

    _, kwargs = mock_analyze.call_args
    assert kwargs.get("model") is None
