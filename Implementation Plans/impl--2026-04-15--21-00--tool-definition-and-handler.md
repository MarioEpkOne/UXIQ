# Implementation Plan: Tool Definition & Public Handler

## Header
- **Spec**: specs/applied/spec--2026-04-15--20-45--tool-definition-and-handler.md
- **Worktree**: (this is a Python-only project with no git worktrees; implement directly in the package)
- **Scope — files in play** (agent must not touch files not listed here):
  - `ui-analyzer/ui_analyzer/tool_definition.py` ← NEW FILE
  - `ui-analyzer/ui_analyzer/handler.py` ← NEW FILE
  - `ui-analyzer/ui_analyzer/__init__.py` ← update `__all__`
  - `ui-analyzer/tests/test_handler.py` ← NEW FILE (per testing strategy)
- **Reading list** (read these in order before starting, nothing else):
  1. `ui-analyzer/ui_analyzer/__init__.py`
  2. `ui-analyzer/ui_analyzer/exceptions.py`
  3. `ui-analyzer/ui_analyzer/image_source.py`
  4. `ui-analyzer/ui_analyzer/axe_runner.py`
  5. `ui-analyzer/ui_analyzer/context_events.py`
  6. `ui-analyzer/ui_analyzer/prompt_builder.py`
  7. `ui-analyzer/ui_analyzer/prompts.py`
  8. `ui-analyzer/ui_analyzer/xml_parser.py`
  9. `ui-analyzer/ui_analyzer/scorer.py`
  10. `ui-analyzer/ui_analyzer/report_renderer.py`
  11. `ui-analyzer/tests/conftest.py`

## Environment Assumptions Verified

- `pydantic` 2.13.1 installed — `BaseModel`, `field_validator` available
- `anthropic` 0.95.0 installed — `anthropic.Anthropic`, `anthropic.APITimeoutError`, `anthropic.RateLimitError` available
- `pytest` 8.x, `pytest-asyncio` 1.3.0, `pytest-mock` 3.15.1 installed
- `conftest.py` sets `ANTHROPIC_API_KEY=test-key-unit-tests` before imports, so `__init__.py`'s guard will not fire during tests

---

## Steps

### Step 1: Create `tool_definition.py`

**File**: `ui-analyzer/ui_analyzer/tool_definition.py`
**Action**: Create new file

**Full file content**:
```python
"""tool_definition.py — Claude Tool Use JSON schema for analyze_ui_screenshot."""

TOOL_DEFINITION = {
    "name": "analyze_ui_screenshot",
    "description": (
        "Analyzes the visual design and UX of a web UI screenshot. "
        "Returns a structured Markdown report with findings across four tiers: "
        "accessibility (WCAG), visual structure (Gestalt/CRAP), usability "
        "(Nielsen/Norman), and domain-specific patterns. "
        "Does not read source code. Analysis is screenshot-only."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "image_source": {
                "type": "string",
                "description": (
                    "Either a URL (https://...) or an absolute file path to a "
                    "PNG, JPG, or WebP screenshot. If a URL, Playwright captures "
                    "the page and axe-core runs WCAG checks. If a file path, "
                    "Tier 1 results are visually estimated."
                ),
            },
            "app_type": {
                "type": "string",
                "enum": ["web_dashboard", "landing_page", "onboarding_flow", "forms"],
                "description": (
                    "The type of web UI being analyzed. Activates the relevant "
                    "Tier 4 domain pattern module and calibrates scoring expectations."
                ),
            },
        },
        "required": ["image_source", "app_type"],
    },
}
```

**What it does**: Exposes the Claude Tool Use JSON schema as a plain Python dict constant. No classes, no Pydantic — just a dict literal.

**Verification**: `python -c "from ui_analyzer.tool_definition import TOOL_DEFINITION; assert TOOL_DEFINITION['name'] == 'analyze_ui_screenshot'; print('OK')"` exits 0.

---

### Step 2: Create `handler.py`

**File**: `ui-analyzer/ui_analyzer/handler.py`
**Action**: Create new file

**Full file content**:
```python
"""handler.py — Public entry point for the ui-analyzer tool.

Public interface:
    analyze_ui_screenshot(image_source: str, app_type: str) -> str

Returns a Markdown audit report. Raises UIAnalyzerError on hard failures.
Never raises on axe-core failure, malformed XML, or partial Claude output.
"""

from __future__ import annotations

import base64
import logging

import anthropic
from pydantic import BaseModel, field_validator
from typing import Literal

from ui_analyzer.axe_runner import AxeCoreResult, AxeFailure, run_axe
from ui_analyzer.context_events import thread_to_prompt
from ui_analyzer.exceptions import UIAnalyzerError
from ui_analyzer.image_source import resolve
from ui_analyzer.prompt_builder import build_thread
from ui_analyzer.prompts import SYSTEM_PROMPT
from ui_analyzer.report_renderer import render
from ui_analyzer.scorer import compute
from ui_analyzer.xml_parser import parse

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
API_TIMEOUT_S = 60

VALID_APP_TYPES = {"web_dashboard", "landing_page", "onboarding_flow", "forms"}


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    image_source: str
    app_type: Literal["web_dashboard", "landing_page", "onboarding_flow", "forms"]

    @field_validator("app_type")
    @classmethod
    def validate_app_type(cls, v: str) -> str:
        if v not in VALID_APP_TYPES:
            raise ValueError(
                f"app_type must be one of: {', '.join(sorted(VALID_APP_TYPES))}"
            )
        return v


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

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

    # 2. Resolve image (raises UIAnalyzerError on hard failure)
    resolved = resolve(req.image_source)

    # 3. Run axe-core if URL; skip entirely if file
    axe_result: AxeCoreResult | AxeFailure | None = None
    if resolved.source_type == "url":
        axe_result = run_axe(req.image_source)
        if isinstance(axe_result, AxeFailure):
            logger.warning("axe-core failed: %s — continuing in estimated mode", axe_result.reason)

    # 4. Build context event thread
    events = build_thread(
        app_type=req.app_type,
        source_type=resolved.source_type,
        image_source_value=req.image_source,
        viewport_width=resolved.width_px,
        viewport_height=resolved.height_px,
        axe_result=axe_result,
    )

    # 5. Assemble user message text from events
    user_text = thread_to_prompt(events)

    # 6. Encode image as base64
    image_b64 = _to_base64(resolved.bytes)
    media_type = _media_type(req.image_source)

    # 7. Call Claude API
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            timeout=API_TIMEOUT_S,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": user_text,
                        },
                    ],
                }
            ],
        )
    except anthropic.APITimeoutError:
        raise UIAnalyzerError(f"Anthropic API call timed out after {API_TIMEOUT_S}s.")
    except anthropic.RateLimitError:
        raise UIAnalyzerError("Anthropic API rate limit hit. Retry after a moment.")

    # 8. Parse Claude's XML response
    audit_report = parse(response.content[0].text)

    # 9. Compute scores
    scores = compute(audit_report)

    # 10. Determine axe_succeeded flag
    axe_succeeded = isinstance(axe_result, AxeCoreResult)

    # 11. Render and return Markdown report
    return render(
        report=audit_report,
        scores=scores,
        app_type=req.app_type,
        image_source=req.image_source,
        axe_succeeded=axe_succeeded,
        model=MODEL,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _to_base64(image_bytes: bytes) -> str:
    """Base64-encode image bytes to a UTF-8 string."""
    return base64.b64encode(image_bytes).decode("utf-8")


def _media_type(image_source: str) -> str:
    """Derive MIME type from image source.

    URL (Playwright always captures PNG) → "image/png"
    .jpg / .jpeg → "image/jpeg"
    .webp → "image/webp"
    Default → "image/png"
    """
    lower = image_source.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/png"
```

**What it does**:
- `AnalyzeRequest` validates inputs via Pydantic v2; `ValidationError` propagates unwrapped.
- `analyze_ui_screenshot()` orchestrates the full pipeline: resolve → axe → build_thread → thread_to_prompt → Claude API → parse → compute → render.
- `_to_base64()` base64-encodes image bytes.
- `_media_type()` derives MIME type: URLs always produce `"image/png"` (Playwright captures PNG), file paths use extension.
- `MODEL` and `API_TIMEOUT_S` are module-level constants used in `messages.create()`.
- `anthropic.Anthropic()` is instantiated per-call.
- `APITimeoutError` and `RateLimitError` are caught and re-raised as `UIAnalyzerError`.

**Verification**: `python -c "from ui_analyzer.handler import analyze_ui_screenshot, MODEL, API_TIMEOUT_S; assert MODEL == 'claude-sonnet-4-6'; assert API_TIMEOUT_S == 60; print('OK')"` exits 0.

---

### Step 3: Update `__init__.py` to export the new public symbols

**File**: `ui-analyzer/ui_analyzer/__init__.py`

**Current value (verified from `/mnt/c/Users/Epkone/UXIQ/ui-analyzer/ui_analyzer/__init__.py`)**:
```python
import os
from ui_analyzer.exceptions import UIAnalyzerError

if not os.getenv("ANTHROPIC_API_KEY"):
    raise UIAnalyzerError("ANTHROPIC_API_KEY environment variable not set.")

__all__ = ["UIAnalyzerError"]
```

**After**:
```python
import os
from ui_analyzer.exceptions import UIAnalyzerError

if not os.getenv("ANTHROPIC_API_KEY"):
    raise UIAnalyzerError("ANTHROPIC_API_KEY environment variable not set.")

from ui_analyzer.handler import analyze_ui_screenshot
from ui_analyzer.tool_definition import TOOL_DEFINITION

__all__ = ["UIAnalyzerError", "analyze_ui_screenshot", "TOOL_DEFINITION"]
```

**What it does**: Makes `analyze_ui_screenshot` and `TOOL_DEFINITION` importable directly from `ui_analyzer`. The `ANTHROPIC_API_KEY` guard runs before the imports — this ordering is intentional so the guard fires before any submodule tries to connect.

**Verification**: `python -c "from ui_analyzer import analyze_ui_screenshot, TOOL_DEFINITION, UIAnalyzerError; print('OK')"` exits 0 (with `ANTHROPIC_API_KEY` set).

---

### Step 4: Create `tests/test_handler.py`

**File**: `ui-analyzer/tests/test_handler.py`
**Action**: Create new file

This is the test suite required by the spec's Testing Strategy. All external I/O (Playwright, Claude API) is mocked.

**Full file content**:
```python
"""Tests for handler.py — analyze_ui_screenshot() orchestration.

All Playwright and Anthropic API calls are mocked.
Tests cover the 7 scenarios specified in Spec 08.
"""
from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from ui_analyzer.axe_runner import AxeCoreResult, AxeFailure
from ui_analyzer.exceptions import UIAnalyzerError
from ui_analyzer.handler import _media_type, _to_base64, analyze_ui_screenshot
from ui_analyzer.image_source import ResolvedImage
from ui_analyzer.xml_parser import AuditReport


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

MINIMAL_VALID_XML = """\
<audit_report>
  <confidence level="medium">Visible content assessed.</confidence>
  <inventory>Two buttons, one heading.</inventory>
  <structure_observation>Left-aligned layout.</structure_observation>
  <tier1_findings></tier1_findings>
  <tier2_findings></tier2_findings>
  <tier3_findings></tier3_findings>
  <tier4_findings></tier4_findings>
</audit_report>
"""

MALFORMED_XML = "Claude says: sorry, cannot produce XML today."

_FAKE_IMAGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # 108 bytes fake PNG


def _make_resolved_file() -> ResolvedImage:
    return ResolvedImage(
        bytes=_FAKE_IMAGE_BYTES,
        source_type="file",
        width_px=800,
        height_px=600,
    )


def _make_resolved_url() -> ResolvedImage:
    return ResolvedImage(
        bytes=_FAKE_IMAGE_BYTES,
        source_type="url",
        width_px=1280,
        height_px=800,
    )


def _make_claude_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    resp = MagicMock()
    resp.content = [content_block]
    return resp


# ---------------------------------------------------------------------------
# Scenario 1: valid file path → returns str with all four tier section headers
# ---------------------------------------------------------------------------

def test_valid_file_path_returns_markdown_with_all_tiers(fixtures_dir, mocker):
    """Valid file path → Markdown str containing all four tier section headers."""
    file_path = f"{fixtures_dir}/dashboard_good.png"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        MINIMAL_VALID_XML
    )

    result = analyze_ui_screenshot(file_path, "web_dashboard")

    assert isinstance(result, str)
    assert "## Tier 1" in result
    assert "## Tier 2" in result
    assert "## Tier 3" in result
    assert "## Tier 4" in result


# ---------------------------------------------------------------------------
# Scenario 2: valid URL → Tier 1 mode shows "Authoritative (axe-core)"
# ---------------------------------------------------------------------------

def test_valid_url_axe_success_shows_authoritative(mocker):
    """Valid URL with axe success → report header shows 'Authoritative (axe-core)'."""
    url = "https://example.com"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_url(),
    )
    mocker.patch(
        "ui_analyzer.handler.run_axe",
        return_value=AxeCoreResult(findings=[]),
    )
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        MINIMAL_VALID_XML
    )

    result = analyze_ui_screenshot(url, "landing_page")

    assert "Authoritative (axe-core)" in result


# ---------------------------------------------------------------------------
# Scenario 3: axe-core failure (mocked) → returns str with ESTIMATED labels, no exception
# ---------------------------------------------------------------------------

def test_axe_failure_returns_string_not_exception(mocker):
    """AxeFailure from run_axe → report returned (no exception), ESTIMATED mode."""
    url = "https://example.com"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_url(),
    )
    mocker.patch(
        "ui_analyzer.handler.run_axe",
        return_value=AxeFailure(reason="axe-core JS injection failed"),
    )
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        MINIMAL_VALID_XML
    )

    result = analyze_ui_screenshot(url, "forms")

    assert isinstance(result, str)
    # axe_succeeded=False → renderer uses "Estimated (visual)"
    assert "Estimated (visual)" in result


# ---------------------------------------------------------------------------
# Scenario 4: malformed XML from Claude → returns str with warning, no exception
# ---------------------------------------------------------------------------

def test_malformed_xml_returns_string_with_warning(fixtures_dir, mocker):
    """Malformed XML from Claude → report str returned with parse warning block."""
    file_path = f"{fixtures_dir}/form.png"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        MALFORMED_XML
    )

    result = analyze_ui_screenshot(file_path, "onboarding_flow")

    assert isinstance(result, str)
    # render() adds a warning block when parse_warnings is non-empty
    assert "malformed" in result.lower() or "warning" in result.lower() or "⚠️" in result


# ---------------------------------------------------------------------------
# Scenario 5: API timeout (mocked) → raises UIAnalyzerError
# ---------------------------------------------------------------------------

def test_api_timeout_raises_ui_analyzer_error(fixtures_dir, mocker):
    """APITimeoutError from Claude → UIAnalyzerError raised."""
    import anthropic as _anthropic

    file_path = f"{fixtures_dir}/dashboard_bad.png"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.side_effect = _anthropic.APITimeoutError(
        request=MagicMock()
    )

    with pytest.raises(UIAnalyzerError, match="timed out"):
        analyze_ui_screenshot(file_path, "web_dashboard")


# ---------------------------------------------------------------------------
# Scenario 6: API rate limit (mocked) → raises UIAnalyzerError
# ---------------------------------------------------------------------------

def test_api_rate_limit_raises_ui_analyzer_error(fixtures_dir, mocker):
    """RateLimitError from Claude → UIAnalyzerError raised."""
    import anthropic as _anthropic

    file_path = f"{fixtures_dir}/landing_page.png"

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch(
        "ui_analyzer.handler.anthropic.Anthropic"
    )
    mock_create.return_value.messages.create.side_effect = _anthropic.RateLimitError(
        message="rate limit", response=MagicMock(), body=None
    )

    with pytest.raises(UIAnalyzerError, match="rate limit"):
        analyze_ui_screenshot(file_path, "landing_page")


# ---------------------------------------------------------------------------
# Scenario 7: invalid app_type → Pydantic ValidationError before any API/Playwright call
# ---------------------------------------------------------------------------

def test_invalid_app_type_raises_validation_error_before_any_io(mocker):
    """Invalid app_type → Pydantic ValidationError raised; resolve() never called."""
    mock_resolve = mocker.patch("ui_analyzer.handler.resolve")

    with pytest.raises(ValidationError):
        analyze_ui_screenshot("/some/path.png", "not_a_valid_type")

    mock_resolve.assert_not_called()


# ---------------------------------------------------------------------------
# Unit tests for private helpers
# ---------------------------------------------------------------------------

def test_to_base64_roundtrips():
    data = b"hello world"
    encoded = _to_base64(data)
    assert base64.b64decode(encoded) == data


def test_media_type_url_always_png():
    assert _media_type("https://example.com") == "image/png"
    assert _media_type("http://example.com/page") == "image/png"


def test_media_type_jpg():
    assert _media_type("/path/to/shot.jpg") == "image/jpeg"
    assert _media_type("/path/to/shot.jpeg") == "image/jpeg"
    assert _media_type("/PATH/TO/SHOT.JPG") == "image/jpeg"


def test_media_type_webp():
    assert _media_type("/path/to/shot.webp") == "image/webp"


def test_media_type_png_and_default():
    assert _media_type("/path/to/shot.png") == "image/png"
    assert _media_type("/path/to/shot.bmp") == "image/png"  # default
```

**What it does**: Tests all 7 spec scenarios plus private helpers `_to_base64` and `_media_type`. Uses `mocker` from `pytest-mock` to patch Playwright and Anthropic calls. Uses fixtures from `conftest.py` (`fixtures_dir`).

**Notes on Scenario 5 & 6 mock construction**:
- `anthropic.APITimeoutError` requires a `request` kwarg.
- `anthropic.RateLimitError` requires `message`, `response`, and `body` kwargs.
If these constructors differ in the installed `anthropic` 0.95.0 SDK, the implementer should inspect `anthropic.APITimeoutError.__init__` and adjust accordingly. An alternative is to use `side_effect = _anthropic.APITimeoutError` with a pre-built instance or use `mocker.patch` with `side_effect=lambda *a, **kw: (_ for _ in ()).throw(_anthropic.APITimeoutError(...))`.

**Verification**: `cd ui-analyzer && pytest tests/test_handler.py -v` exits 0 with 13 tests passing.

---

### Step 5: Run the full test suite

**Action**: Run all tests to confirm no regressions.

```bash
cd /mnt/c/Users/Epkone/UXIQ/ui-analyzer && pytest -v
```

**Expected**: All tests pass (including the pre-existing `test_image_source.py` and `test_xml_parser.py`). Zero failures.

---

## Post-Implementation Checklist

- [ ] `tool_definition.py` exists and `TOOL_DEFINITION["name"] == "analyze_ui_screenshot"`
- [ ] `tool_definition.py` has all four `app_type` enum values: `web_dashboard`, `landing_page`, `onboarding_flow`, `forms`
- [ ] `handler.py` exists with `analyze_ui_screenshot`, `MODEL = "claude-sonnet-4-6"`, `API_TIMEOUT_S = 60`
- [ ] `analyze_ui_screenshot()` is synchronous (no `async def`)
- [ ] `anthropic.Anthropic()` is instantiated inside `analyze_ui_screenshot()`, not at module level
- [ ] `max_tokens=4096` is passed to `client.messages.create()`
- [ ] `APITimeoutError` → `UIAnalyzerError` with "timed out" in message
- [ ] `RateLimitError` → `UIAnalyzerError` with "rate limit" in message
- [ ] `ValidationError` for invalid `app_type` is NOT wrapped — propagates directly
- [ ] `AxeFailure` → `axe_succeeded=False` → render shows "Estimated (visual)"
- [ ] `axe_result=None` (file mode) → `axe_succeeded=False` → render shows "Estimated (visual)"
- [ ] `AxeCoreResult` → `axe_succeeded=True` → render shows "Authoritative (axe-core)"
- [ ] `parse_warnings` non-empty → render includes ⚠️ warning block
- [ ] `__init__.py` exports `analyze_ui_screenshot` and `TOOL_DEFINITION` in `__all__`
- [ ] `pytest tests/test_handler.py -v` exits 0 (all 13 tests pass)
- [ ] `pytest -v` exits 0 (full suite, no regressions)

## Verification Approach

After each step, run:
```bash
cd /mnt/c/Users/Epkone/UXIQ/ui-analyzer
python -c "import ui_analyzer"   # should exit 0 (ANTHROPIC_API_KEY must be set)
```

After Step 4 (test file created):
```bash
cd /mnt/c/Users/Epkone/UXIQ/ui-analyzer
ANTHROPIC_API_KEY=test-key pytest tests/test_handler.py -v
```

After Step 5 (full suite):
```bash
cd /mnt/c/Users/Epkone/UXIQ/ui-analyzer
ANTHROPIC_API_KEY=test-key pytest -v
```

## Commit Message (draft)
```
feat: implement tool_definition.py and handler.py (spec-08)

Adds the two public-surface files for the ui_analyzer package:
- tool_definition.py: TOOL_DEFINITION dict for Claude Tool Use
- handler.py: analyze_ui_screenshot() orchestrating all prior modules
- __init__.py: exports analyze_ui_screenshot and TOOL_DEFINITION
- tests/test_handler.py: 13 unit tests covering all 7 spec scenarios
```
