# Implementation Plan: CLI Entry Point (`uxiq`)

## Header
- **Spec**: specs/applied/spec--2026-04-16--14-30--cli-entry-point.md
- **Worktree**: .claude/worktrees/cli-entry-point/
- **Scope — files in play** (agent must not touch files not listed here):
  - `ui-analyzer/ui_analyzer/__init__.py`
  - `ui-analyzer/ui_analyzer/handler.py`
  - `ui-analyzer/ui_analyzer/cli.py`  ← new file
  - `ui-analyzer/pyproject.toml`
  - `ui-analyzer/tests/conftest.py`
  - `ui-analyzer/tests/test_cli.py`  ← new file
- **Reading list** (read these in order before starting, nothing else):
  1. `ui-analyzer/ui_analyzer/__init__.py`
  2. `ui-analyzer/ui_analyzer/handler.py`
  3. `ui-analyzer/ui_analyzer/exceptions.py`
  4. `ui-analyzer/pyproject.toml`
  5. `ui-analyzer/tests/conftest.py`
  6. `ui-analyzer/tests/test_handler.py`

## Environment Assumptions Verified

- `pytest`, `pytest-asyncio`, `pytest-mock` are declared as `[project.optional-dependencies] dev` in `pyproject.toml` (lines 17–21).
- `asyncio_mode = "auto"` is set in `[tool.pytest.ini_options]` — all tests in the suite are async-safe.
- `importlib.metadata` is stdlib (Python ≥ 3.8) — no new dependency.
- `argparse` is stdlib — no new dependency.
- `pydantic` is already a runtime dependency — `ValidationError` is importable in `cli.py`.
- **Existing conftest.py bug**: `conftest.py` line 8 sets `os.environ["ANTHROPIC_API_KEY"] = "test-key-unit-tests"` but `__init__.py` checks `UXIQ_ANTHROPIC_API_KEY`. This workaround is currently broken — once the env check moves to `handler.py` (Step 1), `__init__.py` imports the package unconditionally and the conftest workaround becomes irrelevant. Step 5 removes the now-dead guard from `conftest.py`.

---

## Steps

### Step 1: Remove import-time env var check from `__init__.py`

**File**: `ui-analyzer/ui_analyzer/__init__.py`
**Action**: Remove the `os` import and the env var guard. Keep all exports intact.

**Current value (verified from `/mnt/c/Users/Epkone/UXIQ/ui-analyzer/ui_analyzer/__init__.py`):**
```python
import os
from ui_analyzer.exceptions import UIAnalyzerError

if not os.getenv("UXIQ_ANTHROPIC_API_KEY"):
    raise UIAnalyzerError("UXIQ_ANTHROPIC_API_KEY environment variable not set.")

from ui_analyzer.handler import analyze_ui_screenshot
from ui_analyzer.tool_definition import TOOL_DEFINITION

__all__ = ["UIAnalyzerError", "analyze_ui_screenshot", "TOOL_DEFINITION"]
```

**After**:
```python
from ui_analyzer.exceptions import UIAnalyzerError
from ui_analyzer.handler import analyze_ui_screenshot
from ui_analyzer.tool_definition import TOOL_DEFINITION

__all__ = ["UIAnalyzerError", "analyze_ui_screenshot", "TOOL_DEFINITION"]
```

**What it does**: Package can now be imported (for `--version`, `list-app-types`) without `UXIQ_ANTHROPIC_API_KEY` being set. The env check will be enforced in `handler.py` (Step 2).

**Invariant preserved**: `UIAnalyzerError`, `analyze_ui_screenshot`, and `TOOL_DEFINITION` remain exported.

**Verification**: `python3 -c "import ui_analyzer; print('ok')"` must print `ok` without `UXIQ_ANTHROPIC_API_KEY` set.

---

### Step 2: Add env var check inside `analyze_ui_screenshot()` in `handler.py`

**File**: `ui-analyzer/ui_analyzer/handler.py`
**Location**: Inside `analyze_ui_screenshot()`, before step 1 (input validation). Also add `os` import verification — `os` is already imported on line 14.

**Current value (verified from `/mnt/c/Users/Epkone/UXIQ/ui-analyzer/ui_analyzer/handler.py`):**
```python
def analyze_ui_screenshot(image_source: str, app_type: str) -> str:
    """Orchestrate a full UI analysis and return a Markdown report.

    Args:
        image_source: A URL (https://...) or absolute file path to a screenshot.
        app_type: One of "web_dashboard", "landing_page", "onboarding_flow", "forms".

    Returns:
        str — Markdown report. Always a string on soft failure (axe failure,
        malformed XML). Never returns None.

    Raises:
        pydantic.ValidationError: if image_source or app_type are invalid (before
            any Playwright/API call).
        UIAnalyzerError: on hard failure — URL 404/timeout/blank, file not found,
            API timeout, or API rate limit.
    """
    # 1. Validate inputs (ValidationError propagates — not wrapped)
    req = AnalyzeRequest(image_source=image_source, app_type=app_type)
```

**After** — insert env check before step 1:
```python
def analyze_ui_screenshot(image_source: str, app_type: str) -> str:
    """Orchestrate a full UI analysis and return a Markdown report.

    Args:
        image_source: A URL (https://...) or absolute file path to a screenshot.
        app_type: One of "web_dashboard", "landing_page", "onboarding_flow", "forms".

    Returns:
        str — Markdown report. Always a string on soft failure (axe failure,
        malformed XML). Never returns None.

    Raises:
        pydantic.ValidationError: if image_source or app_type are invalid (before
            any Playwright/API call).
        UIAnalyzerError: on hard failure — URL 404/timeout/blank, file not found,
            API timeout, or API rate limit.
    """
    # 0. Guard: API key must be set before any work begins
    if not os.getenv("UXIQ_ANTHROPIC_API_KEY"):
        raise UIAnalyzerError("UXIQ_ANTHROPIC_API_KEY environment variable is not set.")

    # 1. Validate inputs (ValidationError propagates — not wrapped)
    req = AnalyzeRequest(image_source=image_source, app_type=app_type)
```

**What it does**: Raises `UIAnalyzerError` immediately (before Pydantic validation, before Playwright, before the API call) if the key is absent. Behavior is identical to before for callers using the library directly — they always needed the key to call `analyze_ui_screenshot`.

**Verification**: `python3 -c "from ui_analyzer.handler import analyze_ui_screenshot; analyze_ui_screenshot('x.png', 'forms')"` must raise `UIAnalyzerError` with message containing "not set".

---

### Step 3: Create `ui-analyzer/ui_analyzer/cli.py`

**File**: `ui-analyzer/ui_analyzer/cli.py` (new file)
**Action**: Create the full CLI module.

```python
"""cli.py — Command-line entry point for uxiq.

Usage:
    uxiq analyze <image_source> --app-type <type> [-o <output>]
    uxiq list-app-types
    uxiq --version
"""
from __future__ import annotations

import argparse
import sys
from importlib.metadata import version, PackageNotFoundError

from pydantic import ValidationError

from ui_analyzer.exceptions import UIAnalyzerError

VALID_APP_TYPES = ["forms", "landing_page", "onboarding_flow", "web_dashboard"]


def main() -> None:
    """Entry point registered in pyproject.toml."""
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)


def _cmd_analyze(args: argparse.Namespace) -> None:
    """Handle `uxiq analyze <image_source> --app-type <type> [-o <path>]`."""
    from ui_analyzer.handler import analyze_ui_screenshot

    try:
        report = analyze_ui_screenshot(args.image_source, args.app_type)
    except ValidationError as exc:
        # Invalid app_type value (already caught by argparse choices, but belt+suspenders)
        app_type_val = args.app_type
        print(
            f"Invalid app-type: {app_type_val!r}. "
            f"Valid: {', '.join(VALID_APP_TYPES)}",
            file=sys.stderr,
        )
        sys.exit(1)
    except UIAnalyzerError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(report)
        except OSError as exc:
            print(f"Error writing output file: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        print(report)


def _cmd_list_app_types(args: argparse.Namespace) -> None:
    """Handle `uxiq list-app-types`."""
    for app_type in VALID_APP_TYPES:
        print(app_type)


def _cmd_no_subcommand(args: argparse.Namespace) -> None:
    """Handle `uxiq` with no subcommand — print help and exit 0."""
    args._parser.print_help()
    sys.exit(0)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uxiq",
        description="UI accessibility and UX auditor powered by Claude.",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=_get_version(),
    )

    subparsers = parser.add_subparsers(dest="subcommand")

    # uxiq analyze
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze a UI screenshot or URL and produce a Markdown audit report.",
    )
    analyze_parser.add_argument(
        "image_source",
        help="Path to a local image file or a URL (https://...).",
    )
    analyze_parser.add_argument(
        "--app-type", "-t",
        dest="app_type",
        required=True,
        choices=VALID_APP_TYPES,
        metavar="APP_TYPE",
        help=f"Type of app being audited. One of: {', '.join(VALID_APP_TYPES)}",
    )
    analyze_parser.add_argument(
        "--output", "-o",
        dest="output",
        default=None,
        help="Optional path to write the Markdown report. Defaults to stdout.",
    )
    analyze_parser.set_defaults(func=_cmd_analyze)

    # uxiq list-app-types
    list_parser = subparsers.add_parser(
        "list-app-types",
        help="Print all valid app types.",
    )
    list_parser.set_defaults(func=_cmd_list_app_types)

    # Default: no subcommand → print help
    parser.set_defaults(func=lambda args: (args.__setattr__("_parser", parser), _cmd_no_subcommand(args)))

    return parser


def _get_version() -> str:
    try:
        v = version("ui-analyzer")
    except PackageNotFoundError:
        v = "unknown"
    return f"uxiq {v}"
```

**What it does**:
- `main()` is the registered entry point. Builds the parser, dispatches to a subcommand function.
- `_cmd_analyze` calls `analyze_ui_screenshot`, catches `UIAnalyzerError` and `ValidationError`, writes to file or stdout.
- `_cmd_list_app_types` prints the four valid app types in alphabetical order.
- `_cmd_no_subcommand` prints help and exits 0.
- `_build_parser` defines the full argument tree with `argparse`.
- `_get_version` reads version from `importlib.metadata`; falls back to `"unknown"` if not installed.
- The `analyze` subparser uses `choices=VALID_APP_TYPES` so argparse itself rejects invalid values with exit code 2 and a usage message. The `ValidationError` catch in `_cmd_analyze` is belt-and-suspenders only.

**Note on invalid app-type behavior**: The spec's edge case table says invalid `--app-type` should result in a `pydantic.ValidationError` caught → exit 1. However, because `argparse choices=` is used, argparse will reject the value with exit code 2 before `_cmd_analyze` is ever called. This is the correct behavior — argparse's built-in error message will say "invalid choice: X (choose from ...)" which is equally informative. The `ValidationError` catch in `_cmd_analyze` remains as a defense against a hypothetical future where `choices=` is removed, but in normal operation the argparse guard fires first.

**Verification**: `python3 -m ui_analyzer.cli --version` must print `uxiq 0.1.0`. `python3 -m ui_analyzer.cli list-app-types` must print 4 lines.

---

### Step 4: Register `uxiq` script in `pyproject.toml`

**File**: `ui-analyzer/pyproject.toml`
**Location**: After the `[project]` section, before `[project.optional-dependencies]`

**Current value (verified from `/mnt/c/Users/Epkone/UXIQ/ui-analyzer/pyproject.toml`):**
```toml
[project]
name = "ui-analyzer"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.25.0",
    "playwright>=1.43.0",
    "pillow>=10.0.0",
    "pyyaml>=6.0",
    "pydantic>=2.0",
]

[project.optional-dependencies]
```

**After** — insert `[project.scripts]` between `[project]` and `[project.optional-dependencies]`:
```toml
[project.scripts]
uxiq = "ui_analyzer.cli:main"

[project.optional-dependencies]
```

**What it does**: After `pip install -e ".[dev]"`, the `uxiq` command is available in the environment's PATH.

**Verification**: After running `pip install -e ".[dev]"`, `uxiq --version` must output `uxiq 0.1.0`.

---

### Step 5: Fix `conftest.py` — remove the now-broken env var workaround

**File**: `ui-analyzer/tests/conftest.py`
**Action**: Remove the `ANTHROPIC_API_KEY` workaround. It was added to prevent an import-time `UIAnalyzerError` when `UXIQ_ANTHROPIC_API_KEY` was unset — but it was setting the wrong environment variable (`ANTHROPIC_API_KEY` instead of `UXIQ_ANTHROPIC_API_KEY`), so it was already broken. After Step 1, `__init__.py` no longer raises at import time, making this guard unnecessary entirely.

**Current value (verified from `/mnt/c/Users/Epkone/UXIQ/ui-analyzer/tests/conftest.py`):**
```python
import os
import pytest

# IMPORTANT: ui_analyzer/__init__.py raises UIAnalyzerError at import time
# if ANTHROPIC_API_KEY is unset. Set a fake key before any ui_analyzer import
# so that unit tests (which mock the API) can import the package.
# This must happen before pytest collects test modules.
if not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "test-key-unit-tests"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as requiring a real ANTHROPIC_API_KEY"
    )


@pytest.fixture
def fixtures_dir():
    return os.path.join(os.path.dirname(__file__), "fixtures")
```

**After**:
```python
import os
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as requiring a real ANTHROPIC_API_KEY"
    )


@pytest.fixture
def fixtures_dir():
    return os.path.join(os.path.dirname(__file__), "fixtures")
```

**What it does**: Removes the dead guard that set `ANTHROPIC_API_KEY`. Existing unit tests in `test_handler.py` mock `anthropic.Anthropic` directly (via `mocker.patch`), so they do not need the real `UXIQ_ANTHROPIC_API_KEY`. The `skip_if_no_key` guard in `test_handler.py` checks `ANTHROPIC_API_KEY` — this is a separate issue in the existing code, not in scope for this spec.

**Verification**: `pytest tests/` (without `UXIQ_ANTHROPIC_API_KEY` set) must import successfully and all non-integration tests must pass.

---

### Step 6: Create `ui-analyzer/tests/test_cli.py`

**File**: `ui-analyzer/tests/test_cli.py` (new file)
**Action**: Create unit tests for the CLI. Uses `subprocess.run` to invoke `python3 -m ui_analyzer.cli` — this avoids argparse `SystemExit` complications when calling `main()` directly in-process, and exercises the full CLI dispatch path.

```python
"""Tests for cli.py — uxiq command-line interface.

All tests invoke via subprocess to avoid in-process SystemExit complications.
No UXIQ_ANTHROPIC_API_KEY is required for any test in this file.
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

def test_analyze_invalid_app_type_exits_2_mentions_valid():
    """uxiq analyze file.png --app-type badvalue → exit 2, stderr mentions valid choices."""
    result = _run("analyze", "file.png", "--app-type", "badvalue")
    assert result.returncode == 2
    # argparse prints "invalid choice: badvalue" with the valid choices list
    assert "badvalue" in result.stderr or "invalid choice" in result.stderr


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
# UXIQ_ANTHROPIC_API_KEY not set → list-app-types still works
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
# UXIQ_ANTHROPIC_API_KEY not set → --version still works
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
```

**What it does**:
- Tests 1–2: `--version` and `list-app-types` via subprocess — exercises full dispatch path.
- Tests 3–4: argparse error paths — missing `--app-type` and invalid value; both exit 2.
- Tests 5–7: in-process unit tests using `patch` on `analyze_ui_screenshot` for `UIAnalyzerError`, successful `-o` write, and `OSError` on bad output path.
- Test 8: no subcommand → help + exit 0.
- Tests 9–10: `--version` and `list-app-types` work without `UXIQ_ANTHROPIC_API_KEY` set — directly validates the env check move from Step 1/2.

**Note on test 4 (invalid app-type)**: The spec's edge case table says invalid `--app-type` exits 1 with "Valid: forms, ..." message. However, because `choices=` is used in `_build_parser`, argparse rejects invalid values with exit code 2 before `_cmd_analyze` runs. The test asserts exit 2 (the actual behavior with `choices=`), which is consistent with how argparse works. The spec's description of the error format (mentioning valid app types in a custom message) is superseded by the Technical Design decision to use `argparse` with `choices=` — argparse's own error message includes the valid choices list.

---

## Post-Implementation Checklist

- [ ] `python3 -c "import ui_analyzer; print('ok')"` prints `ok` without `UXIQ_ANTHROPIC_API_KEY` set
- [ ] `python3 -m ui_analyzer.cli --version` prints `uxiq 0.1.0` and exits 0
- [ ] `python3 -m ui_analyzer.cli list-app-types` prints 4 lines (forms, landing_page, onboarding_flow, web_dashboard) and exits 0
- [ ] `python3 -m ui_analyzer.cli analyze screenshot.png --app-type web_dashboard` (without API key): prints error to stderr, exits 1
- [ ] `python3 -m ui_analyzer.cli analyze screenshot.png` (no --app-type): exits 2, stderr mentions `--app-type`
- [ ] `python3 -m ui_analyzer.cli analyze screenshot.png --app-type invalid`: exits 2, stderr mentions invalid value
- [ ] `python3 -m ui_analyzer.cli` (no subcommand): exits 0, help text in stdout
- [ ] `pip install -e ".[dev]"` re-run; `uxiq --version` available in PATH
- [ ] `pytest ui-analyzer/tests/` (without API key): all unit tests pass, integration tests skipped
- [ ] `__init__.py` still exports `UIAnalyzerError`, `analyze_ui_screenshot`, `TOOL_DEFINITION`
- [ ] No new runtime dependencies introduced

## Verification Approach

After each file change, run:
```bash
cd /mnt/c/Users/Epkone/UXIQ/ui-analyzer
python3 -m py_compile ui_analyzer/<changed_file>.py
```

After Step 1 (\_\_init\_\_.py change):
```bash
python3 -c "import ui_analyzer; print('ok')"
```

After Step 3 (cli.py creation):
```bash
python3 -m ui_analyzer.cli --version
python3 -m ui_analyzer.cli list-app-types
```

After Step 4 (pyproject.toml) + reinstall:
```bash
pip install -e ".[dev]"
uxiq --version
uxiq list-app-types
```

Final test run:
```bash
cd /mnt/c/Users/Epkone/UXIQ/ui-analyzer
pytest tests/ -v
```

## Commit Message (draft)
```
feat: add uxiq CLI entry point with analyze, list-app-types, and --version

Adds ui_analyzer/cli.py with argparse subcommands. Moves the
UXIQ_ANTHROPIC_API_KEY env check from __init__.py into
analyze_ui_screenshot() so --version and list-app-types work without
the API key. Registers the uxiq script in pyproject.toml.
```
