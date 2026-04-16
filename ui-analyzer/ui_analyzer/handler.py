"""handler.py — Public entry point for the ui-analyzer tool.

Public interface:
    analyze_ui_screenshot(image_source: str, app_type: str, verify: bool = True, progress: ProgressCallback | None = None) -> str

Returns a Markdown audit report. Raises UIAnalyzerError on hard failures.
Never raises on axe-core failure, malformed XML, or partial Claude output.
"""

from __future__ import annotations

import base64
import ipaddress
import logging
import os
import re
import socket
from urllib.parse import urlparse

import anthropic
from pydantic import BaseModel, field_validator
from typing import Literal, Protocol

from ui_analyzer.axe_runner import AxeCoreResult, AxeFailure, run_axe
from ui_analyzer.context_events import thread_to_prompt
from ui_analyzer.dom_extractor import DomElements, DomFailure, extract_dom
from ui_analyzer.exceptions import UIAnalyzerError
from ui_analyzer.image_source import resolve
from ui_analyzer.prompt_builder import build_thread
from ui_analyzer.prompts import SYSTEM_PROMPT
from ui_analyzer.report_renderer import render
from ui_analyzer.utils import safe_log_url
from ui_analyzer.verifier import run_verification
from ui_analyzer.run_writer import RunUsage, write_run
from ui_analyzer.scorer import compute
from ui_analyzer.xml_parser import parse

# Regex-tolerant search for <audit_report> open tag (handles attributed variants)
_AUDIT_REPORT_OPEN_RE = re.compile(r"<audit_report(?:\s[^>]*)?>")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# URL guard helpers
# ---------------------------------------------------------------------------

_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"})

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_image_url(url: str) -> bool:
    """Return True if the URL path ends with a known image file extension.

    Comparison is case-insensitive. Only the path component is checked —
    query strings and fragments are ignored.
    """
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in _IMAGE_EXTENSIONS)


def _check_ssrf(url: str) -> None:
    """Resolve the URL hostname and raise UIAnalyzerError if it maps to a blocked network.

    Blocked networks: loopback, private RFC-1918, link-local (including
    169.254.169.254 IMDS), and IPv6 loopback/link-local.

    Raises UIAnalyzerError on SSRF match, unresolvable hostname, or missing hostname.
    """
    hostname = urlparse(url).hostname
    if not hostname:
        raise UIAnalyzerError(f"Cannot resolve hostname for URL: {url}")
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(hostname))
    except (socket.gaierror, ValueError) as e:
        raise UIAnalyzerError(f"Cannot resolve hostname '{hostname}': {e}")
    if any(ip in net for net in _BLOCKED_NETWORKS):
        raise UIAnalyzerError(
            f"URL resolves to a blocked address ({ip}). "
            "Internal/loopback/link-local URLs are not permitted."
        )


class ProgressCallback(Protocol):
    """Duck-typed protocol for pipeline progress reporting.

    Implementations must provide stage_start and stage_end.
    The handler calls these at the start and end of each pipeline stage.
    No ABC or hard import required — duck-typed.
    """

    def stage_start(self, stage: str, label: str) -> None: ...
    def stage_end(self, stage: str, label: str, elapsed: float, detail: str = "") -> None: ...

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

def analyze_ui_screenshot(
    image_source: str,
    app_type: str,
    verify: bool = True,
    progress: ProgressCallback | None = None,
) -> str:
    """Orchestrate a full UI analysis and return a Markdown report.

    Args:
        image_source: A URL (http:// or https://) to a live page. File paths
            are not accepted and will raise pydantic.ValidationError.
        app_type: One of "web_dashboard", "landing_page", "onboarding_flow", "forms".
        verify: If True (default), run a second Claude pass to verify and amend
            the primary audit findings. Set to False to skip verification and
            reduce cost (saves ~10-15% of per-call token cost).
        progress: Optional progress callback. When provided, stage_start and
            stage_end are called at each pipeline stage boundary. When None
            (default), no progress output is produced and existing callers
            are unaffected.

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
    import time as _time  # local import to avoid polluting module namespace

    # 0. Validate inputs (ValidationError propagates — not wrapped)
    req = AnalyzeRequest(image_source=image_source, app_type=app_type, verify=verify)

    # 1. Guard: API key must be set before any work begins
    if not os.getenv("UXIQ_ANTHROPIC_API_KEY"):
        raise UIAnalyzerError("UXIQ_ANTHROPIC_API_KEY environment variable is not set.")

    # 0b. SSRF guard — raises UIAnalyzerError for internal/loopback/link-local addresses
    _check_ssrf(req.image_source)

    # 0c. Image-file URL guard — soft failure; disables axe+DOM for image URLs
    _url_is_image = _is_image_url(req.image_source)

    # 2. Resolve image (raises UIAnalyzerError on hard failure)
    if progress is not None:
        progress.stage_start("image", "Loading image...")
    _t0 = _time.monotonic()
    resolved = resolve(req.image_source)
    if progress is not None:
        progress.stage_end("image", "Image loaded", _time.monotonic() - _t0)

    # 3. Run axe-core (skipped for image URLs — axe requires a live webpage)
    if progress is not None:
        progress.stage_start("axe", "Running accessibility checks...")
    _t0 = _time.monotonic()
    if _url_is_image:
        axe_result: AxeCoreResult | AxeFailure = AxeFailure(
            reason="URL points to an image file, not a webpage — axe-core requires a live page"
        )
    else:
        axe_result = run_axe(req.image_source)
    if isinstance(axe_result, AxeFailure):
        logger.warning("axe-core failed: %s — continuing in estimated mode", axe_result.reason)

    # 3b. Extract DOM elements (skipped for image URLs)
    if _url_is_image:
        dom_result: DomElements | DomFailure = DomFailure(
            reason="URL points to an image file, not a webpage"
        )
    else:
        dom_result = extract_dom(req.image_source)
    if isinstance(dom_result, DomFailure):
        logger.warning("DOM extraction failed: %s — continuing without DOM data", dom_result.reason)

    if progress is not None:
        _axe_detail = ""
        if isinstance(axe_result, AxeCoreResult):
            _n_violations = sum(1 for f in axe_result.findings if f.result == "FAIL")
            if _n_violations > 0:
                _axe_detail = f"{_n_violations} violation(s) found"
        progress.stage_end("axe", "Accessibility checks done", _time.monotonic() - _t0, _axe_detail)

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

    if progress is not None:
        progress.stage_start("claude", "Analysing with Claude...")
    _t0 = _time.monotonic()
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
    if progress is not None:
        progress.stage_end("claude", "Analysis complete", _time.monotonic() - _t0)

    primary_usage = response.usage

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

    # 9b. Log raw response head if primary parse failed (diagnostic for future debugging)
    if audit_report.parse_warnings:
        logger.warning(
            "Primary parse failed (%s) — raw response head: %.500s",
            audit_report.parse_warnings,
            raw_text,
        )

    # 9a. Warn if inventory is empty — verifier will be instructed to populate it
    if not audit_report.inventory:
        logger.warning(
            "Primary audit produced no inventory for %s — verifier will be instructed to populate it.",
            safe_log_url(req.image_source),
        )

    # 9.5. Verification pass — second Claude call that peer-reviews the primary output
    verifier_usage = None
    if req.verify:
        if progress is not None:
            progress.stage_start("verify", "Running verification pass...")
        _t0 = _time.monotonic()
        audit_report, verifier_usage = run_verification(
            client=client,
            system=system_cacheable,
            user_content=user_content_cacheable,
            primary_raw_text=raw_text,
            audit_report=audit_report,
        )
        if progress is not None:
            progress.stage_end("verify", "Verification complete", _time.monotonic() - _t0)

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
    run_usage = RunUsage(
        primary_input_tokens=getattr(primary_usage, "input_tokens", 0),
        primary_output_tokens=getattr(primary_usage, "output_tokens", 0),
        primary_cache_write_tokens=getattr(primary_usage, "cache_creation_input_tokens", 0) or 0,
        primary_cache_read_tokens=getattr(primary_usage, "cache_read_input_tokens", 0) or 0,
        verifier_input_tokens=getattr(verifier_usage, "input_tokens", 0) if verifier_usage else 0,
        verifier_output_tokens=getattr(verifier_usage, "output_tokens", 0) if verifier_usage else 0,
        verifier_cache_write_tokens=getattr(verifier_usage, "cache_creation_input_tokens", 0) if verifier_usage else 0,
        verifier_cache_read_tokens=getattr(verifier_usage, "cache_read_input_tokens", 0) if verifier_usage else 0,
    )
    write_run(
        url=req.image_source,
        app_type=req.app_type,
        model=MODEL,
        report=audit_report,
        rendered_output=output,
        usage=run_usage,
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
    Handles attributed variants like <audit_report version="1">.
    """
    m = _AUDIT_REPORT_OPEN_RE.search(raw)
    if not m:
        # No XML block at all — treat entire response as preamble.
        return raw.strip()
    return raw[:m.start()].strip()
