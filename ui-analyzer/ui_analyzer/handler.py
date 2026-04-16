"""handler.py — Public entry point for the ui-analyzer tool.

Public interface:
    analyze_ui_screenshot(image_source: str, app_type: str, verify: bool = True) -> str

Returns a Markdown audit report. Raises UIAnalyzerError on hard failures.
Never raises on axe-core failure, malformed XML, or partial Claude output.
"""

from __future__ import annotations

import base64
import logging
import os

import anthropic
from pydantic import BaseModel, field_validator
from typing import Literal

from ui_analyzer.axe_runner import AxeCoreResult, AxeFailure, run_axe
from ui_analyzer.context_events import thread_to_prompt
from ui_analyzer.dom_extractor import DomElements, DomFailure, extract_dom
from ui_analyzer.exceptions import UIAnalyzerError
from ui_analyzer.image_source import resolve
from ui_analyzer.prompt_builder import build_thread
from ui_analyzer.prompts import SYSTEM_PROMPT
from ui_analyzer.report_renderer import render
from ui_analyzer.verifier import run_verification
from ui_analyzer.run_writer import write_run
from ui_analyzer.scorer import compute
from ui_analyzer.xml_parser import parse

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16_384
API_TIMEOUT_S = 180

VALID_APP_TYPES = {"web_dashboard", "landing_page", "onboarding_flow", "forms"}


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    image_source: str
    app_type: Literal["web_dashboard", "landing_page", "onboarding_flow", "forms"]
    verify: bool = True

    @field_validator("image_source")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("image_source must be a URL (http:// or https://)")
        return v

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

def analyze_ui_screenshot(image_source: str, app_type: str, verify: bool = True) -> str:
    """Orchestrate a full UI analysis and return a Markdown report.

    Args:
        image_source: A URL (http:// or https://) to a live page. File paths
            are not accepted and will raise pydantic.ValidationError.
        app_type: One of "web_dashboard", "landing_page", "onboarding_flow", "forms".
        verify: If True (default), run a second Claude pass to verify and amend
            the primary audit findings. Set to False to skip verification and
            reduce cost (saves ~10-15% of per-call token cost).

    Returns:
        str — Markdown report. Always a string on soft failure (axe failure,
        DOM extraction failure, malformed XML). Never returns None.
        A debug Markdown file is written to runs/ after each successful analysis.

    Raises:
        pydantic.ValidationError: if image_source is not a URL, or app_type is
            invalid (before any Playwright/API call).
        UIAnalyzerError: on hard failure — URL 404/timeout/blank, API timeout,
            or API rate limit.
    """
    # 0. Validate inputs (ValidationError propagates — not wrapped)
    req = AnalyzeRequest(image_source=image_source, app_type=app_type, verify=verify)

    # 1. Guard: API key must be set before any work begins
    if not os.getenv("UXIQ_ANTHROPIC_API_KEY"):
        raise UIAnalyzerError("UXIQ_ANTHROPIC_API_KEY environment variable is not set.")

    # 2. Resolve image (raises UIAnalyzerError on hard failure)
    resolved = resolve(req.image_source)

    # 3. Run axe-core (always runs — URL-only guarantee)
    axe_result: AxeCoreResult | AxeFailure | None = run_axe(req.image_source)
    if isinstance(axe_result, AxeFailure):
        logger.warning("axe-core failed: %s — continuing in estimated mode", axe_result.reason)

    # 3b. Extract DOM elements (always runs — URL-only guarantee)
    dom_result: DomElements | DomFailure = extract_dom(req.image_source)
    if isinstance(dom_result, DomFailure):
        logger.warning("DOM extraction failed: %s — continuing without DOM data", dom_result.reason)

    # 4. Build context event thread
    events = build_thread(
        app_type=req.app_type,
        source_type=resolved.source_type,
        image_source_value=req.image_source,
        viewport_width=resolved.width_px,
        viewport_height=resolved.height_px,
        axe_result=axe_result,
        dom_result=dom_result,
    )

    # 5. Assemble user message text from events
    user_text = thread_to_prompt(events)

    # 6. Encode image as base64
    image_b64 = _to_base64(resolved.bytes)
    media_type = _media_type(req.image_source)

    # 7. Call Claude API (with prompt caching so the verifier call can reuse tokens cheaply)
    client = anthropic.Anthropic(api_key=os.getenv("UXIQ_ANTHROPIC_API_KEY"))

    # Build cacheable system and user content structures
    system_cacheable = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    user_content_cacheable = [
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
            "cache_control": {"type": "ephemeral"},
        },
    ]

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            timeout=API_TIMEOUT_S,
            system=system_cacheable,
            messages=[
                {
                    "role": "user",
                    "content": user_content_cacheable,
                }
            ],
        )
    except anthropic.APITimeoutError:
        raise UIAnalyzerError(f"Anthropic API call timed out after {API_TIMEOUT_S}s.")
    except anthropic.RateLimitError:
        raise UIAnalyzerError("Anthropic API rate limit hit. Retry after a moment.")

    # 7b. Detect truncation before attempting any parsing
    if response.stop_reason == "max_tokens":
        raise UIAnalyzerError(
            f"Claude's response was cut off — the audit exceeded the {MAX_TOKENS}-token "
            "output ceiling. Try a simpler screenshot or contact support."
        )

    # 8. Extract preamble (text before <audit_report>) from raw response
    raw_text = response.content[0].text
    preamble = _extract_preamble(raw_text)

    # 9. Parse Claude's XML response
    audit_report = parse(raw_text)

    # 9.5. Verification pass — second Claude call that peer-reviews the primary output
    if req.verify:
        audit_report = run_verification(
            client=client,
            system=system_cacheable,
            user_content=user_content_cacheable,
            primary_raw_text=raw_text,
            audit_report=audit_report,
        )

    # 10. Compute scores
    scores = compute(audit_report)

    # 11. Determine axe_succeeded flag
    axe_succeeded = isinstance(axe_result, AxeCoreResult)

    # 12. Render Markdown report
    output = render(
        report=audit_report,
        scores=scores,
        app_type=req.app_type,
        image_source=req.image_source,
        axe_succeeded=axe_succeeded,
        model=MODEL,
    )

    # 12b. Write per-run debug file (soft failure — never raises)
    write_run(
        url=req.image_source,
        app_type=req.app_type,
        model=MODEL,
        report=audit_report,
        rendered_output=output,
    )

    # 13. Prepend preamble if present
    if preamble:
        output = preamble + "\n\n" + output

    return output


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


def _extract_preamble(raw: str) -> str:
    """Return any text Claude wrote before <audit_report>, stripped.

    Returns '' if there is no such text or if the string is empty.
    """
    start = raw.find("<audit_report>")
    if start == -1:
        # No XML block at all — treat entire response as preamble.
        return raw.strip()
    return raw[:start].strip()
