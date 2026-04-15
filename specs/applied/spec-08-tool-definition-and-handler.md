# Spec 08 — Tool Definition & Public Handler

**Parent spec:** spec--2026-04-15--15-30--ui-screenshot-analyzer.md  
**Status:** Ready for implementation  
**Depends on:** Specs 01–07 (all prior modules)  
**Blocks:** Spec 09 (integration tests call analyze_ui_screenshot())

---

## Goal

Implement the two files that constitute the public surface of the tool:

1. **`tool_definition.py`** — the Claude Tool Use JSON schema (`TOOL_DEFINITION`)
2. **`handler.py`** — `analyze_ui_screenshot()` — the orchestrating function that calls all prior modules and returns the Markdown report

---

## Scope

Files created by this spec:

```
ui_analyzer/
├── tool_definition.py
└── handler.py
```

---

## tool_definition.py

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

`TOOL_DEFINITION` is the only export from this module. It is a plain Python dict — not a Pydantic model, not a class.

---

## handler.py

### Input validation

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

Pydantic validation runs before any Playwright or API call. A `ValidationError` from Pydantic is not wrapped in `UIAnalyzerError` — callers get the Pydantic error directly (this is a caller contract violation, not a runtime failure).

### analyze_ui_screenshot()

```python
import anthropic
import logging
from ui_analyzer.exceptions import UIAnalyzerError
from ui_analyzer.image_source import resolve
from ui_analyzer.axe_runner import run_axe, AxeCoreResult, AxeFailure
from ui_analyzer.prompt_builder import build_thread
from ui_analyzer.context_events import thread_to_prompt
from ui_analyzer.prompts import SYSTEM_PROMPT
from ui_analyzer.xml_parser import parse
from ui_analyzer.scorer import compute
from ui_analyzer.report_renderer import render

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
API_TIMEOUT_S = 60

def analyze_ui_screenshot(image_source: str, app_type: str) -> str:
    """Analyze a UI screenshot and return a Markdown report.

    Returns:
        str — Markdown report (always, on success or degraded completion)

    Raises UIAnalyzerError on hard failures only:
        - URL load failure (404, timeout, blank page)
        - File not found or unsupported type
        - ANTHROPIC_API_KEY not set (raised at import time by __init__.py)
        - Anthropic API timeout or rate limit
    """
```

### Orchestration sequence

```python
# 1. Validate inputs
request = AnalyzeRequest(image_source=image_source, app_type=app_type)

# 2. Resolve image source (may raise UIAnalyzerError on hard failure)
resolved = resolve(request.image_source)

# 3. Run axe-core (URL mode only; returns AxeCoreResult or AxeFailure)
axe_result = None   # stays None for file mode
if resolved.source_type == "url":
    axe_result = run_axe(request.image_source)
    if isinstance(axe_result, AxeFailure):
        logger.warning("axe-core failed for %s (%s) — proceeding in estimated mode",
                       request.image_source, axe_result.reason)

# 4. Assemble context thread
events = build_thread(
    app_type=request.app_type,
    source_type=resolved.source_type,
    image_source_value=request.image_source,
    viewport_width=resolved.width_px,
    viewport_height=resolved.height_px,
    axe_result=axe_result,
)
user_text = thread_to_prompt(events)

# 5. Call Anthropic API
client = anthropic.Anthropic()
try:
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": _media_type(request.image_source),
                        "data": _to_base64(resolved.bytes),
                    },
                },
                {
                    "type": "text",
                    "text": user_text,
                },
            ],
        }],
        timeout=API_TIMEOUT_S,
    )
except anthropic.APITimeoutError:
    raise UIAnalyzerError(f"Anthropic API call timed out after {API_TIMEOUT_S}s.")
except anthropic.RateLimitError:
    raise UIAnalyzerError("Anthropic API rate limit hit. Retry after a moment.")

# 6. Parse Claude response
claude_text = response.content[0].text
audit_report = parse(claude_text)

# 7. Compute scores
scores = compute(audit_report)

# 8. Render Markdown
markdown = render(
    report=audit_report,
    scores=scores,
    app_type=request.app_type,
    image_source=request.image_source,
    axe_succeeded=isinstance(axe_result, AxeCoreResult),
    model=MODEL,
)
return markdown
```

### Private helpers

```python
import base64
import mimetypes

def _to_base64(image_bytes: bytes) -> str:
    return base64.standard_b64encode(image_bytes).decode("utf-8")

def _media_type(image_source: str) -> str:
    """Derive MIME type for Claude's image source block.

    URL mode: Playwright always captures PNG regardless of the URL's extension.
    File mode: extension determines the type.
    Check URL prefix first so that URL paths ending in .jpg still return image/png.
    """
    lower = image_source.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return "image/png"  # Playwright screenshot is always PNG
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/png"  # .png or any other accepted type defaults to PNG
```

For URL inputs, Playwright always captures PNG. For file inputs, the extension drives the MIME type.

---

## Return Type Contract (invariant from parent spec)

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

## Browser Lifecycle Invariant

`resolve()` and `run_axe()` each launch and close their own independent Playwright browser instance. They are called sequentially by the handler — `resolve()` first, then `run_axe()`. There is no shared browser context.

---

## Concurrency

Concurrent calls to `analyze_ui_screenshot()` are supported. Each call runs its own isolated Playwright browsers (one in `resolve()`, one in `run_axe()`). No module-level mutable state is used. The `anthropic.Anthropic()` client is instantiated per-call — not shared.

---

## Constraints

- `MODEL = "claude-sonnet-4-6"` is a module-level constant in `handler.py`. It must not be hardcoded as a string literal in the `messages.create()` call.
- `API_TIMEOUT_S = 60` is a module-level constant.
- `max_tokens=4096` is fixed in v1.
- Do not add retry logic for API failures in v1 — surface the error immediately.
- `analyze_ui_screenshot()` must not be `async` — it is synchronous throughout.

---

## Success Criteria

Covered by tests in Spec 09. Key assertions:

- [ ] Valid file path → returns `str` containing all four tier section headers
- [ ] Valid URL → Tier 1 mode in report shows "Authoritative (axe-core)"
- [ ] axe-core failure (mocked) → returns `str` with ESTIMATED labels, no exception raised
- [ ] Malformed XML from Claude (mocked) → returns `str` with ⚠️ warning, no exception raised
- [ ] API timeout (mocked) → raises `UIAnalyzerError`
- [ ] API rate limit (mocked) → raises `UIAnalyzerError`
- [ ] Invalid `app_type` → Pydantic `ValidationError` raised before any API/Playwright call
