# Spec — Tool Definition & Public Handler

**Source:** spec-08-tool-definition-and-handler.md  
**Date:** 2026-04-15  
**Status:** Ready for implementation  
**Depends on:** Specs 01–07 (all prior modules implemented)  
**Blocks:** Spec 09 (integration tests call analyze_ui_screenshot())

---

## Goal

Implement the two files that constitute the public surface of the `ui_analyzer` tool:

1. **`ui_analyzer/tool_definition.py`** — the Claude Tool Use JSON schema (`TOOL_DEFINITION`)
2. **`ui_analyzer/handler.py`** — `analyze_ui_screenshot()` — the orchestrating function that calls all prior modules and returns the Markdown report

---

## Current State

All dependency modules are already implemented in `ui-analyzer/ui_analyzer/`:
- `exceptions.py` — `UIAnalyzerError`
- `image_source.py` — `resolve()`
- `axe_runner.py` — `run_axe()`, `AxeCoreResult`, `AxeFailure`
- `context_events.py` — `thread_to_prompt()`
- `prompt_builder.py` — `build_thread()`
- `prompts.py` — `SYSTEM_PROMPT`
- `xml_parser.py` — `parse()`
- `scorer.py` — `compute()`
- `report_renderer.py` — `render()`
- `__init__.py` — raises `UIAnalyzerError` if `ANTHROPIC_API_KEY` not set

Missing: `tool_definition.py` and `handler.py`.

---

## Decisions

- `TOOL_DEFINITION` is a plain Python dict — not Pydantic, not a class.
- Pydantic validates inputs before any Playwright/API call; `ValidationError` is not wrapped.
- `analyze_ui_screenshot()` is synchronous (not async).
- `anthropic.Anthropic()` client is instantiated per-call (no sharing).
- No retry logic in v1 — surface errors immediately.
- `MODEL = "claude-sonnet-4-6"` and `API_TIMEOUT_S = 60` are module-level constants.

---

## Technical Design

### tool_definition.py

```python
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

### handler.py — Input Validation

```python
from pydantic import BaseModel, field_validator
from typing import Literal

VALID_APP_TYPES = {"web_dashboard", "landing_page", "onboarding_flow", "forms"}

class AnalyzeRequest(BaseModel):
    image_source: str
    app_type: Literal["web_dashboard", "landing_page", "onboarding_flow", "forms"]

    @field_validator("app_type")
    @classmethod
    def validate_app_type(cls, v):
        if v not in VALID_APP_TYPES:
            raise ValueError(
                f"app_type must be one of: {', '.join(sorted(VALID_APP_TYPES))}"
            )
        return v
```

### handler.py — Orchestration sequence

1. Validate inputs with `AnalyzeRequest`
2. `resolve(image_source)` → may raise `UIAnalyzerError`
3. If URL: `run_axe(image_source)` → `AxeCoreResult` or `AxeFailure` (log warning, continue)
4. `build_thread(...)` → events list
5. `thread_to_prompt(events)` → user_text string
6. `client.messages.create(...)` with image (base64) + text content blocks
7. `parse(response.content[0].text)` → audit_report
8. `compute(audit_report)` → scores
9. `render(report, scores, app_type, image_source, axe_succeeded, model)` → markdown
10. Return markdown

### handler.py — Private helpers

- `_to_base64(image_bytes: bytes) -> str` — base64 encode
- `_media_type(image_source: str) -> str` — derive MIME type:
  - URL → always `"image/png"` (Playwright always captures PNG)
  - `.jpg`/`.jpeg` → `"image/jpeg"`
  - `.webp` → `"image/webp"`
  - Default → `"image/png"`

### handler.py — Exception handling

- `anthropic.APITimeoutError` → raise `UIAnalyzerError(f"Anthropic API call timed out after {API_TIMEOUT_S}s.")`
- `anthropic.RateLimitError` → raise `UIAnalyzerError("Anthropic API rate limit hit. Retry after a moment.")`

---

## Return Type Contract

| Scenario | Return |
|----------|--------|
| Success | `str` (full Markdown report) |
| axe-core fails | `str` (degraded report with ESTIMATED labels) |
| Claude returns malformed XML | `str` (partial report with ⚠️ warning) |
| URL 404 / timeout / blank | raises `UIAnalyzerError` |
| File not found / bad type | raises `UIAnalyzerError` |
| API timeout | raises `UIAnalyzerError` |
| API rate limit | raises `UIAnalyzerError` |

`analyze_ui_screenshot()` **never** raises `UIAnalyzerError` for axe-core failure, malformed XML, or partial Claude output.

---

## Edge Cases & Error Handling

- `AxeFailure` from `run_axe()` → log warning, set `axe_result = AxeFailure(...)`, continue
- `axe_result = None` for file mode → `axe_succeeded=False` in `render()`
- `axe_result = AxeFailure(...)` → `axe_succeeded=False` in `render()`
- `axe_result = AxeCoreResult(...)` → `axe_succeeded=True` in `render()`
- Pydantic `ValidationError` on bad `app_type` is NOT wrapped — propagates directly

---

## Constraints & Invariants

- `MODEL = "claude-sonnet-4-6"` — module-level constant, not string literal in create()
- `API_TIMEOUT_S = 60` — module-level constant
- `max_tokens = 4096` — fixed
- No retry logic for API failures
- `analyze_ui_screenshot()` must be synchronous
- `resolve()` and `run_axe()` are called sequentially; each manages its own Playwright browser
- `anthropic.Anthropic()` client instantiated per-call

---

## Testing Strategy

Tests covered by Spec 09. Key assertions:
- Valid file path → returns `str` with all four tier section headers
- Valid URL → Tier 1 mode shows "Authoritative (axe-core)"
- axe-core failure (mocked) → returns `str` with ESTIMATED labels, no exception
- Malformed XML from Claude (mocked) → returns `str` with ⚠️ warning, no exception
- API timeout (mocked) → raises `UIAnalyzerError`
- API rate limit (mocked) → raises `UIAnalyzerError`
- Invalid `app_type` → Pydantic `ValidationError` before any API/Playwright call

---

## Open Questions

None — spec is complete and unambiguous.
