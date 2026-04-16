"""run_writer.py — Write a per-run debug Markdown file to runs/ at project root.

Public interface:
    write_run(url: str, app_type: str, model: str,
              report: AuditReport, rendered_output: str) -> None

Always soft-failure: never raises. On any error, logs a warning and returns.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from ui_analyzer.xml_parser import AuditReport

logger = logging.getLogger(__name__)

# Project root is three levels up from this file:
#   ui_analyzer/run_writer.py → ui_analyzer/ → ui-analyzer/ → UXIQ/
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_RUNS_DIR = _PROJECT_ROOT / "runs"


def _source_slug(url: str) -> str:
    """Derive a filesystem-safe slug from a URL.

    Takes hostname + first non-empty path segment, replaces non-alphanumeric
    chars with hyphens, collapses consecutive hyphens, strips leading/trailing
    hyphens, and truncates at 40 characters.

    Examples:
        "https://example.com"               → "example-com"
        "https://example.com/dashboard/v2"  → "example-com-dashboard"
        "https://foo.bar.com/path?q=1"      → "foo-bar-com-path"
    """
    # Strip scheme
    without_scheme = re.sub(r"^https?://", "", url)
    # Remove query string and fragment
    without_query = re.split(r"[?#]", without_scheme)[0]
    # Split into parts: hostname + path segments
    parts = [p for p in without_query.replace("/", " ").split() if p]
    # Take hostname + first path segment only
    slug_parts = parts[:2] if len(parts) > 1 else parts[:1]
    raw = "-".join(slug_parts)
    # Replace non-alphanumeric (except hyphens) with hyphens
    raw = re.sub(r"[^a-zA-Z0-9\-]", "-", raw)
    # Collapse consecutive hyphens
    raw = re.sub(r"-{2,}", "-", raw)
    # Strip leading/trailing hyphens and truncate
    return raw.strip("-")[:40]


def _iso_timestamp() -> str:
    """Return a filesystem-safe UTC ISO timestamp (colons → hyphens)."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")


def write_run(
    url: str,
    app_type: str,
    model: str,
    report: AuditReport,
    rendered_output: str,
) -> None:
    """Write a debug Markdown file to runs/ for this analysis run.

    Soft failure: any exception is caught, logged as a warning, and the
    function returns normally. Never raises.
    """
    try:
        slug = _source_slug(url)
        timestamp = _iso_timestamp()
        filename = f"{slug}_{timestamp}.md"

        os.makedirs(_RUNS_DIR, exist_ok=True)
        filepath = _RUNS_DIR / filename

        confidence_level = report.confidence_level or "—"
        confidence_reason = report.confidence_reason or "—"
        inventory = report.inventory or "*Claude produced no inventory.*"
        structure_observation = (
            report.structure_observation
            or "*Claude produced no structure observation.*"
        )

        content = f"""# UI Analysis Run

**URL:** {url}
**App type:** {app_type}
**Run timestamp:** {timestamp} UTC
**Model:** {model}

---

## What Claude Sees

### Confidence
**Level:** {confidence_level}
**Reason:** {confidence_reason}

### Inventory
{inventory}

### Structure Observation
{structure_observation}

---

## Full Analysis

{rendered_output}
"""
        filepath.write_text(content, encoding="utf-8")
        logger.debug("run_writer: wrote debug file to %s", filepath)

    except Exception as exc:
        logger.warning("run_writer: failed to write debug file: %s", exc)
